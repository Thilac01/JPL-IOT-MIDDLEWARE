from remote_exec import sftp_write, run_remote_command

script = """
import os
import pymysql
from dotenv import load_dotenv
load_dotenv(override=True)
from app.db.tunnel import SSHTunnelManager
import asyncio

async def test():
    mgr = SSHTunnelManager()
    ok = await mgr.start()
    if ok:
        try:
            user = os.environ.get("REPLICA_USER")
            pwd = os.environ.get("REPLICA_PASSWORD")
            db = os.environ.get("REPLICA_DB", "koha_jpl")
            conn = pymysql.connect(host="127.0.0.1", port=mgr.local_bind_port, user=user, password=pwd, db=db, cursorclass=pymysql.cursors.DictCursor)
            with conn.cursor() as cur:
                print("=== COLUMNS IN items ===")
                cur.execute("DESCRIBE items;")
                items_cols = [r['Field'] for r in cur.fetchall()]
                print([c for c in items_cols if any(k in c.lower() for k in ['bar', 'year', 'date', 'pub'])])
                
                print("=== COLUMNS IN biblio ===")
                cur.execute("DESCRIBE biblio;")
                bib_cols = [r['Field'] for r in cur.fetchall()]
                print([c for c in bib_cols if any(k in c.lower() for k in ['year', 'date', 'pub', 'copy'])])

                print("=== COLUMNS IN biblioitems ===")
                cur.execute("DESCRIBE biblioitems;")
                bi_cols = [r['Field'] for r in cur.fetchall()]
                print([c for c in bi_cols if any(k in c.lower() for k in ['year', 'date', 'pub'])])

                print("=== SAMPLE ROW IN issues JOIN ===")
                cur.execute('''
                    SELECT i.issue_id, it.barcode, b.title, b.copyrightdate, bi.publicationyear, p.firstname, p.surname, i.issuedate, i.date_due
                    FROM issues i
                    JOIN items it ON i.itemnumber = it.itemnumber
                    JOIN biblio b ON it.biblionumber = b.biblionumber
                    LEFT JOIN biblioitems bi ON b.biblionumber = bi.biblionumber
                    JOIN borrowers p ON i.borrowernumber = p.borrowernumber
                    LIMIT 3;
                ''')
                for r in cur.fetchall():
                    print(r)

                print("=== SAMPLE ROW IN old_issues JOIN ===")
                cur.execute('''
                    SELECT oi.issue_id, it.barcode, b.title, b.copyrightdate, bi.publicationyear, p.firstname, p.surname, oi.returndate
                    FROM old_issues oi
                    JOIN items it ON oi.itemnumber = it.itemnumber
                    JOIN biblio b ON it.biblionumber = b.biblionumber
                    LEFT JOIN biblioitems bi ON b.biblionumber = bi.biblionumber
                    JOIN borrowers p ON oi.borrowernumber = p.borrowernumber
                    LIMIT 3;
                ''')
                for r in cur.fetchall():
                    print(r)

            conn.close()
        except Exception as e:
            print("Error:", e)
        finally:
            await mgr.stop()

if __name__ == "__main__":
    asyncio.run(test())
"""

sftp_write("/JPL_MW/JPL-IOT-MIDDLEWARE/inspect_schema.py", script)
out, err = run_remote_command("./venv/bin/python inspect_schema.py")
print(out)
if err:
    print("STDERR:", err)
