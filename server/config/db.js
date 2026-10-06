const dns = require('dns');
const mongoose = require('mongoose');
const env = require('./env');

// Node's resolver can fail SRV lookups (needed by mongodb+srv:// URIs) on some
// networks even when the OS resolver works. In development, pin the DNS servers.
if (env.nodeEnv !== 'production') {
  dns.setServers(['8.8.8.8', '1.1.1.1']);
}

async function connectDB(uri = env.mongoUri) {
  await mongoose.connect(uri, { serverSelectionTimeoutMS: 15000 });
  console.log(`MongoDB connected: ${mongoose.connection.host}`);
}

module.exports = connectDB;