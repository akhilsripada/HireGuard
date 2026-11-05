"""SQLite stand-in for the DynamoDB tables, used by run.py (local mode) and the handler tests.

It implements only the small part of the DynamoDB Table API the handlers use:
get_item, put_item, update_item (ADD / SET), query on a table index, and scan,
with the expression forms the handlers write:

    KeyConditionExpression  "#k = :v"
    FilterExpression        "#a = :x AND #b >= :y AND attribute_exists(#c)"
    UpdateExpression        "ADD #n :one, #s :set SET #t = :t"

Anything else raises NotImplementedError, so a handler change that needs more is caught by the tests.
Items with an `expiresAt` in the past are treated as deleted, like DynamoDB TTL.
"""
import json
import re
import sqlite3
import threading
import time

# Table name (the handler's env var) -> primary key and indexes (name -> (partition key, sort key)).
SCHEMA = {
    "SCANS_TABLE": ("scanId", {"byDay": ("day", "createdAt")}),
    "REPORTS_TABLE": ("contactHash", {}),
    "DOMAIN_CACHE_TABLE": ("domain", {}),
    "LIBRARY_TABLE": ("entryId", {"byNewest": ("kind", "createdAt")}),
}


def _encode(item: dict) -> str:
    return json.dumps(item, default=lambda v: {"__set__": sorted(v)} if isinstance(v, (set, frozenset)) else str(v))


def _decode(raw: str) -> dict:
    return json.loads(raw, object_hook=lambda d: set(d["__set__"]) if set(d) == {"__set__"} else d)


def _name(token: str, names: dict) -> str:
    return names.get(token, token) if token.startswith("#") else token


def _value(token: str, values: dict):
    if token not in values:
        raise NotImplementedError(f"unknown expression value {token}")
    return values[token]


_COMPARE = re.compile(r"^(#?\w+)\s*(=|>=|<=|>|<)\s*(:\w+)$")
_EXISTS = re.compile(r"^attribute_exists\((#?\w+)\)$")


def _condition(expr: str, names: dict, values: dict):
    """Turn "A AND B AND ..." into a predicate on an item."""
    checks = []
    for part in re.split(r"\s+AND\s+", expr.strip()):
        part = part.strip()
        if m := _COMPARE.match(part):
            attr, op, val = _name(m[1], names), m[2], _value(m[3], values)
            checks.append((attr, op, val))
        elif m := _EXISTS.match(part):
            checks.append((_name(m[1], names), "exists", None))
        else:
            raise NotImplementedError(f"unsupported expression: {part}")

    def test(item: dict) -> bool:
        for attr, op, val in checks:
            if op == "exists":
                if attr not in item:
                    return False
                continue
            if attr not in item:
                return False
            have = item[attr]
            ok = {"=": have == val, ">=": have >= val, "<=": have <= val, ">": have > val, "<": have < val}[op]
            if not ok:
                return False
        return True

    return test


class LocalTable:
    def __init__(self, db: "LocalDatabase", name: str):
        self.db, self.name = db, name
        self.key, self.indexes = SCHEMA[name]

    # ---- helpers ----
    def _live(self, item: dict | None) -> dict | None:
        if item is None:
            return None
        expires = item.get("expiresAt")
        return None if isinstance(expires, (int, float)) and expires < time.time() else item

    def _all(self) -> list[dict]:
        rows = self.db.conn.execute("SELECT data FROM items WHERE tbl = ?", (self.name,)).fetchall()
        return [i for i in (self._live(_decode(r[0])) for r in rows) if i is not None]

    def _get(self, key_value) -> dict | None:
        row = self.db.conn.execute("SELECT data FROM items WHERE tbl = ? AND pk = ?", (self.name, str(key_value))).fetchone()
        return self._live(_decode(row[0])) if row else None

    def _put(self, item: dict) -> None:
        self.db.conn.execute(
            "INSERT INTO items (tbl, pk, data) VALUES (?, ?, ?) ON CONFLICT (tbl, pk) DO UPDATE SET data = excluded.data",
            (self.name, str(item[self.key]), _encode(item)),
        )
        self.db.conn.commit()

    # ---- DynamoDB Table API subset ----
    def get_item(self, Key):  # noqa: N803 - DynamoDB argument names
        with self.db.lock:
            item = self._get(Key[self.key])
        return {"Item": item} if item else {}

    def put_item(self, Item):  # noqa: N803
        with self.db.lock:
            self._put(dict(Item))
        return {}

    def update_item(self, Key, UpdateExpression, ExpressionAttributeNames=None,  # noqa: N803
                    ExpressionAttributeValues=None, ReturnValues="NONE"):
        names, values = ExpressionAttributeNames or {}, ExpressionAttributeValues or {}
        sections = dict(re.findall(r"\b(ADD|SET)\s+(.*?)(?=\s+(?:ADD|SET)\s+|$)", UpdateExpression.strip()))
        rest = re.sub(r"\b(ADD|SET)\s+.*?(?=\s+(?:ADD|SET)\s+|$)", "", UpdateExpression.strip()).strip()
        if rest or not sections:
            raise NotImplementedError(f"unsupported update: {UpdateExpression}")
        with self.db.lock:
            item = self._get(Key[self.key]) or {self.key: Key[self.key]}
            for clause in filter(None, (c.strip() for c in sections.get("ADD", "").split(","))):
                attr, token = clause.split()
                attr, val = _name(attr, names), _value(token, values)
                if isinstance(val, (set, frozenset)):
                    item[attr] = set(item.get(attr, set())) | set(val)
                elif isinstance(val, (int, float)):
                    item[attr] = item.get(attr, 0) + val
                else:
                    raise NotImplementedError("ADD needs a number or a set")
            for clause in filter(None, (c.strip() for c in sections.get("SET", "").split(","))):
                attr, token = (p.strip() for p in clause.split("=", 1))
                item[_name(attr, names)] = _value(token, values)
            self._put(item)
        return {"Attributes": dict(item)} if ReturnValues == "ALL_NEW" else {}

    def query(self, IndexName, KeyConditionExpression, ExpressionAttributeNames=None,  # noqa: N803
              ExpressionAttributeValues=None, FilterExpression=None, ScanIndexForward=True,
              Limit=None, ExclusiveStartKey=None, ProjectionExpression=None):
        names, values = ExpressionAttributeNames or {}, ExpressionAttributeValues or {}
        if IndexName not in self.indexes:
            raise NotImplementedError(f"{self.name} has no index {IndexName}")
        pk, sk = self.indexes[IndexName]
        m = _COMPARE.match(KeyConditionExpression.strip())
        if not m or m[2] != "=" or _name(m[1], names) != pk:
            raise NotImplementedError(f"unsupported key condition: {KeyConditionExpression}")
        want = _value(m[3], values)
        with self.db.lock:
            items = [i for i in self._all() if i.get(pk) == want]
        items.sort(key=lambda i: (str(i.get(sk, "")), str(i[self.key])), reverse=not ScanIndexForward)
        if ExclusiveStartKey:
            ids = [i[self.key] for i in items]
            start = ExclusiveStartKey.get(self.key)
            items = items[ids.index(start) + 1:] if start in ids else []
        page = items[:Limit] if Limit else items
        more = Limit is not None and len(items) > Limit
        if FilterExpression:
            page_out = [i for i in page if _condition(FilterExpression, names, values)(i)]
        else:
            page_out = list(page)
        out = {"Items": page_out}
        if more and page:
            last = page[-1]
            out["LastEvaluatedKey"] = {self.key: last[self.key], pk: last[pk], sk: last.get(sk)}
        return out

    def scan(self, FilterExpression=None, ExpressionAttributeNames=None,  # noqa: N803
             ExpressionAttributeValues=None, ProjectionExpression=None, ExclusiveStartKey=None):
        names, values = ExpressionAttributeNames or {}, ExpressionAttributeValues or {}
        with self.db.lock:
            items = self._all()
        if FilterExpression:
            test = _condition(FilterExpression, names, values)
            items = [i for i in items if test(i)]
        return {"Items": items}


class LocalDatabase:
    """One SQLite file (or ":memory:") holding all four tables."""

    def __init__(self, path: str = ":memory:"):
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.execute("CREATE TABLE IF NOT EXISTS items (tbl TEXT NOT NULL, pk TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY (tbl, pk))")
        self.conn.commit()
        self.tables = {name: LocalTable(self, name) for name in SCHEMA}

    def table(self, env_name: str) -> LocalTable:
        return self.tables[env_name]

    def close(self) -> None:
        self.conn.close()
