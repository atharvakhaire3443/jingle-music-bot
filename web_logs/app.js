const express = require('express');
const sqlite3 = require('sqlite3');
const path = require('path');

const app = express();

// Static files
app.use("/public", express.static(__dirname + "/public"));

const db = new sqlite3.Database('/home/atharva/Documents/jingle-music-bot/jingle.db');

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

app.use(express.static(path.join(__dirname,'views')));

app.get('/', (req, res) => {
    db.all('SELECT name FROM servers', (err, rows) => {
        if (err) {
            console.error(err.message);
            return res.status(500).send('Internal Server Error');
        }

        res.render('index', { servers: rows });
    });
});

app.get('/server/:serverName',(req,res) => {
    const serverName = req.params.serverName;
    console.log('Requested server:', serverName);
    res.render('server',{ serverName })
})

app.listen(3000, () => {
    console.log('Server is running on http://localhost:3000');
});
