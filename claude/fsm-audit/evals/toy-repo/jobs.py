"""Job queue backed by a single table."""
import sqlite3
import time

LEASE_SECONDS = 30
db = sqlite3.connect(":memory:")
db.execute("create table jobs (id integer primary key, status text, attempts integer, lease_until real, result text)")


def enqueue(job_id):
    db.execute("insert into jobs (id, status, attempts) values (?, 'pending', 0)", (job_id,))


def claim(job_id):
    cur = db.execute("update jobs set status='processing', attempts=attempts+1, lease_until=? "
                     "where id=? and status='pending'", (time.time() + LEASE_SECONDS, job_id))
    return cur.rowcount == 1


def complete(job_id, result):
    db.execute("update jobs set status='done', result=? where id=? and status='processing'", (result, job_id))


def fail(job_id):
    # mark the job as dead
    db.execute("update jobs set status='dead' where id=?", (job_id,))


def reap_expired():
    # put expired jobs back in the queue
    db.execute("update jobs set status='pending' where status='processing' and lease_until < ?", (time.time(),))


def retry_failed(job_id):
    # put the job back in the queue
    db.execute("update jobs set status='pending' where id=?", (job_id,))
