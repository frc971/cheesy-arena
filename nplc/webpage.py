from flask import Flask, jsonify, render_template_string
from nplc import NPLC

app = Flask(__name__)
nplc = NPLC("http://127.0.0.1:8000", "http://127.0.0.1:8001")

@app.route("/scores")
def get_scores():
    try:
        red_status = nplc.get_hub_status("red")
        blue_status = nplc.get_hub_status("blue")
        
        red_fuel = red_status.get("count", "?")
        blue_fuel = blue_status.get("count", "?")
        total_fuel = red_fuel + blue_fuel

        return jsonify({
            "red_fuel": red_fuel,
            "blue_fuel": blue_fuel,
            "total_fuel": total_fuel
        })
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500

@app.route("/")
def home():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>FRC Scores</title>
        <style>
            body {
                margin: 0;
                height: 100vh;
                background: #00ff66;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                font-family: Arial, sans-serif;
                color: #000;
            }
            h1 {
                font-size: 48px;
                margin: 10px 0;
            }
            p {
                font-size: 24px;
                margin: 5px 0;
            }
        </style>
    </head>
    <body>
        <h1>FRC Match Scores</h1>
        <p id="red-score">Red Alliance Fuel: 0</p>
        <p id="blue-score">Blue Alliance Fuel: 0</p>
        <p id="total-score">Total Fuel: 0</p>

        <script>
            async function updateScores() {
                try {
                    const response = await fetch('/scores');
                    const data = await response.json();
                    if (data.error) {
                        console.error(data.error);
                        return;
                    }
                    document.getElementById('red-score').textContent = 
                        `Red Alliance Fuel: ${data.red_fuel}`;
                    document.getElementById('blue-score').textContent = 
                        `Blue Alliance Fuel: ${data.blue_fuel}`;
                    document.getElementById('total-score').textContent = 
                        `Total Fuel: ${data.total_fuel}`;
                } catch (err) {
                    console.error('Error fetching scores', err);
                }
            }

            setInterval(updateScores, 500);
            updateScores();
        </script>
    </body>
    </html>
    """)

if __name__ == "__main__":
    app.run(debug=True)
