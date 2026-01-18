from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///history.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(3000), nullable=True)
    created_at = db.Column(db.DateTime(), default=datetime.utcnow)

@app.route("/", methods=['GET','POST'])
def start_page():
    if request.method == 'POST':
        new_message = Message(content=request.form['content'])
        db.session.add(new_message)
        db.session.commit()
    return render_template('index.html')

@app.route("/get_history", methods=['GET'])
def get_History():
    messages = Message.query.order_by(Message.created_at.desc()).all()

    history_data = []
    for msg in messages:
        ts = 0.0
        zeit_str = "--.--.----, --:-- Uhr"
        
        if msg.created_at:
            utc_dt = msg.created_at.replace(tzinfo=timezone.utc)
            
            local_dt = utc_dt.astimezone()
            
            zeit_str = local_dt.strftime("%d.%m.%Y, %H:%M Uhr")
            
            ts = utc_dt.timestamp()

        history_data.append({
            'id': msg.id,
            'timestamp': ts,
            'time': zeit_str,  # Hier steht jetzt die korrekte deutsche Zeit drinnen!
            'message': msg.content
        })
    return jsonify(history_data)

@app.route("/delete_message/<int:id>", methods=['DELETE'])
def delete_message(id):
    msg_to_delete = Message.query.get_or_404(id)
    try:
        db.session.delete(msg_to_delete)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Gelöscht'})
    except:
        return jsonify({'success': False, 'message': 'Fehler beim Löschen'}), 500

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=8000, debug=True)