# flask --app main run
from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
app = Flask(__name__)
app.config ['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///history.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Message(db.Model):
    id = db.Column(db.Integer,primary_key=True)
    content = db.Column(db.String(3000), nullable=True)
    created_at = db.Column(db.DateTime(), default=datetime.utcnow)

@app.route("/", methods=['GET','POST'])
def start_page():
    if request.method =='POST':
        new_message = Message(
            content = request.form['content']
        )
        db.session.add(new_message)
        db.session.commit()
    return render_template('index.html')

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(port=8000,debug=True)
    app.static_folder = 'static'

