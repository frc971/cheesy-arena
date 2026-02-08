from flask import Flask, jsonify, render_template_string
from nplc import NPLC

app = Flask(__name__)
nplc = NPLC("http://127.0.0.1:8000", "http://127.0.0.1:8001")

@app.route("/scores")
def get_scores():
    try:
        red_status = nplc.get_hub_status("red")
        blue_status = nplc.get_hub_status("blue")
        
        red_fuel = red_status.get("count", 0)
        blue_fuel = blue_status.get("count", 0)
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
                background-color: #00ff22; /* full green background */
                font-family: Arial, sans-serif;
                display: flex;
                flex-direction: column;
                justify-content: flex-end; /* push HUD to bottom */
                color: #fff;
            }

            /* HUD container pinned at bottom */
            .hud {
                display: flex;
                justify-content: space-between;
                align-items: center;
                width: 100%;
                padding: 10px 20px;
                box-sizing: border-box;
            }

            .corner-box, .middle-box {
                width: 200px;
                height: 100px;
                display: flex;
                justify-content: center;
                align-items: center;
                font-size: 28px;
                font-weight: bold;
                border-radius: 10px;
                color: #fff;
            }

            .red-box { background-color: rgba(255,0,0,0.8); }
            .blue-box { background-color: rgba(0,0,255,0.8); }
            .middle-box { background-color: rgba(158, 3, 255, 0.6); width: 200px; }
        </style>
    </head>
    <body>
        <div class="hud">
            <div class="corner-box red-box" id="red-score">0</div>
            <div class="middle-box" id="total-score">0</div>
            <div class="corner-box blue-box" id="blue-score">0</div>
        </div>

        <script>
            async function updateScores() {
                try {
                    const response = await fetch('/scores');
                    const data = await response.json();
                    if (data.error) {
                        console.error(data.error);
                        return;
                    }
                    document.getElementById('red-score').textContent = data.red_fuel;
                    document.getElementById('blue-score').textContent = data.blue_fuel;
                    document.getElementById('total-score').textContent = data.total_fuel;
                } catch (err) {
                    console.error('Error fetching scores', err);
                }
            }

            setInterval(updateScores, 800);
            updateScores();
        </script>
    </body>
    </html>
    """)

if __name__ == "__main__":
    app.run(debug=True)
