from server import app, socketio

if __name__ == "__main__":
    socketio.run(app, "0.0.0.0", port=5001, debug=True)
