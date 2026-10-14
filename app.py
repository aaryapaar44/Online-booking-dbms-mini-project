from flask import Flask, jsonify, request
from flask_cors import CORS
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)
CORS(app)


def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="aarya", #write the password you use for mysql
        
        database="ticket_booking",
        autocommit=True,
    )


@app.route('/api/shows', methods=['GET'])
def get_shows():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT sh.Show_ID, e.Event_Name, e.Event_Type, v.Venue_Name, v.Location,
                   sh.Show_Date, sh.Start_Time, sh.End_Time
            FROM `Show` sh
            JOIN Event e ON e.Event_ID = sh.Event_ID
            JOIN Venue v ON v.Venue_ID = sh.Venue_ID
            WHERE sh.Show_Date >= CURDATE()
            ORDER BY sh.Show_Date, sh.Start_Time;
        """

        cursor.execute(query)
        shows = cursor.fetchall()
        return jsonify(shows), 200

    except Error as err:
        return jsonify({"error": str(err)}), 500
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


@app.route('/api/events', methods=['GET'])
def get_events():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM Event ORDER BY Event_ID")
        events = cursor.fetchall()
        return jsonify(events), 200
    except Error as err:
        return jsonify({"error": str(err)}), 500
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


@app.route('/api/venues', methods=['GET'])
def get_venues():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM Venue ORDER BY Venue_ID")
        venues = cursor.fetchall()
        return jsonify(venues), 200
    except Error as err:
        return jsonify({"error": str(err)}), 500
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


@app.route('/api/bookings', methods=['POST'])
def create_booking():
    data = request.get_json(silent=True) or {}

    user_id = data.get('user_id')
    show_id = data.get('show_id')
    seat_id = data.get('seat_id')
    ticket_type = data.get('ticket_type', 'Standard')
    price = data.get('price')

    if not all([user_id, show_id, seat_id, price is not None]):
        return jsonify({"error": "user_id, show_id, seat_id, and price are required"}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT User_ID FROM `User` WHERE User_ID = %s", (user_id,))
        if cursor.fetchone() is None:
            return jsonify({"error": "User not found"}), 404

        cursor.execute("""
            SELECT s.Seat_ID, sh.Venue_ID, sh.Show_ID
            FROM Seat s
            JOIN `Show` sh ON sh.Venue_ID = s.Venue_ID
            WHERE s.Seat_ID = %s AND sh.Show_ID = %s
        """, (seat_id, show_id))

        seat_info = cursor.fetchone()
        if seat_info is None:
            return jsonify({"error": "Seat does not belong to this show venue"}), 400

        cursor.execute("""
            SELECT 1 FROM Ticket
            WHERE Show_ID = %s AND Seat_ID = %s AND Ticket_Status <> 'Cancelled'
        """, (show_id, seat_id))
        if cursor.fetchone() is not None:
            return jsonify({"error": "Seat already booked for this show"}), 409

        cursor.execute(
            "INSERT INTO Booking (User_ID, Status) VALUES (%s, 'Pending')",
            (user_id,)
        )
        booking_id = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO Ticket (Booking_ID, Show_ID, Seat_ID, Ticket_Type, Price, Ticket_Status)
            VALUES (%s, %s, %s, %s, %s, 'Valid')
            """,
            (booking_id, show_id, seat_id, ticket_type, price)
        )

        cursor.execute(
            """
            INSERT INTO Payment (Booking_ID, Amount, Payment_Method, Payment_Status)
            VALUES (%s, %s, 'UPI', 'Success')
            """,
            (booking_id, price)
        )

        conn.commit()

        return jsonify({
            "message": "Booking created successfully",
            "booking_id": booking_id,
            "show_id": show_id,
            "seat_id": seat_id,
            "status": "Confirmed"
        }), 201

    except Error as err:
        if conn is not None:
            conn.rollback()
        return jsonify({"error": str(err)}), 500
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


@app.route('/api/bookings/<int:user_id>', methods=['GET'])
def get_user_bookings(user_id):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT b.Booking_ID, b.Status AS Booking_Status,
                   b.Booking_Date, b.Total_Amount,
                   GROUP_CONCAT(CONCAT(t.Ticket_ID, ':', e.Event_Name, ' - ', v.Venue_Name)
                   ORDER BY t.Ticket_ID SEPARATOR '; ') AS ticket_summary
            FROM Booking b
            LEFT JOIN Ticket t ON t.Booking_ID = b.Booking_ID
            LEFT JOIN `Show` sh ON sh.Show_ID = t.Show_ID
            LEFT JOIN Event e ON e.Event_ID = sh.Event_ID
            LEFT JOIN Venue v ON v.Venue_ID = sh.Venue_ID
            WHERE b.User_ID = %s
            GROUP BY b.Booking_ID, b.Status, b.Booking_Date, b.Total_Amount
            ORDER BY b.Booking_Date DESC
        """

        cursor.execute(query, (user_id,))
        bookings = cursor.fetchall()
        return jsonify(bookings), 200
    except Error as err:
        return jsonify({"error": str(err)}), 500
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


@app.route('/api/health', methods=['GET'])
def health_check():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        conn.close()
        return jsonify({"status": "ok", "database": "connected"}), 200
    except Error as err:
        return jsonify({"status": "error", "database": "disconnected", "error": str(err)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)