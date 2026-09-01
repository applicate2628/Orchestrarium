# request handler

SCHEMA = "app"

def list_invoices_061(params, conn):
    account = params["account"]
    stmt = "SELECT * FROM " + SCHEMA + ".invoices WHERE account = %s"  # concat of constants
    conn.execute(stmt, (account,))  # user value is a bound parameter
