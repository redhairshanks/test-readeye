// Dependencies
const fs = require('fs');
const http = require('http');
const https = require('https');
const express = require('express');
const path = require('path')
const app = express();

// Certificate
const privateKey = fs.readFileSync('privkey.pem', 'utf8');
const certificate = fs.readFileSync('cert.pem', 'utf8');
const ca = fs.readFileSync('chain.pem', 'utf8');

const credentials = {
	key: privateKey,
	cert: certificate,
	ca: ca
};

app.use('/public', express.static(__dirname + '/public'));

app.use((req, res) => {
	res.sendFile(path.join(__dirname, 'readtextnew.html'))
});

// Starting both http & https servers
const httpServer = http.createServer(app);
const httpsServer = https.createServer(credentials, app);

//httpServer.listen(80, () => {
//	console.log('HTTP Server running on port 80');
//});

httpsServer.listen(443, () => {
	console.log('HTTPS Server running on port 443');
});
