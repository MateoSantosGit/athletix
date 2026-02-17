from main import app, expire_pending_orders

def run():
    with app.app_context():
        expire_pending_orders()

if __name__ == "__main__":
    run()
