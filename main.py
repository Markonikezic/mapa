from flask import Flask, send_file
# Uvozimo tvoju funkciju iz generisi_mapu.py fajla koji je u istom folderu
from generisi_mapu import pokreni_generisanje 

app = Flask(__name__)

@app.route("/")
def home():
    # Pokrećemo tvoj kod da preuzme sveže podatke i napravi novu mapu
    pokreni_generisanje() 
    
    # Vraćamo generisanu mapu direktno u browser korisnika
    return send_file("bilans_mreze_danilovgrad.html")

if __name__ == "__main__":
    app.run(debug=True)
