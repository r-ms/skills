"""Job queue backed by a single table, with leases and attempts."""
import sqlite3
import time

LEASE_SECONDS = 30
MAX_ATTEMPTS = 5
db = sqlite3.connect(":memory:")
db.execute("create table jobs (id integer primary key, status text, attempts integer, lease_until real, owner text, result text)")


def enqueue(job_id):
    db.execute("insert into jobs (id, status, attempts) values (?, 'pending', 0)", (job_id,))


def claim(job_id, owner):
    cur = db.execute("update jobs set status='processing', attempts=attempts+1, owner=?, lease_until=? "
                     "where id=? and status='pending' and attempts < ?",
                     (owner, time.time() + LEASE_SECONDS, job_id, MAX_ATTEMPTS))
    return cur.rowcount == 1


def complete(job_id, owner, result):
    cur = db.execute("update jobs set status='done', result=? where id=? and status='processing' and owner=?",
                     (result, job_id, owner))
    if cur.rowcount != 1:
        raise RuntimeError("completion refused: job is not leased by this owner")


def fail(job_id, owner):
    cur = db.execute("update jobs set status='failed' where id=? and status='processing' and owner=?", (job_id, owner))
    return cur.rowcount == 1


def reap_expired():
    # expired leases return to the queue or are marked dead
    db.execute("update jobs set status='pending', owner=null where status='processing' and lease_until < ? and attempts < ?",
               (time.time(), MAX_ATTEMPTS))
    db.execute("update jobs set status='dead' where status='processing' and lease_until < ? and attempts >= ?",
               (time.time(), MAX_ATTEMPTS))


def retry_failed(job_id):
    cur = db.execute("update jobs set status='pending' where id=? and status='failed' and attempts < ?", (job_id, MAX_ATTEMPTS))
    return cur.rowcount == 1
