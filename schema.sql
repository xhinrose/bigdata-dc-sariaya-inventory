DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS devices;
DROP TABLE IF EXISTS device_history;

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT CHECK(role IN ('admin', 'editor')) NOT NULL
);

CREATE TABLE devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_number TEXT UNIQUE NOT NULL,
    serial_number TEXT UNIQUE NOT NULL,
    sim_number TEXT NOT NULL,
    network TEXT CHECK(network IN ('SMART', 'DITO', 'GLOBE')) NOT NULL,
    status TEXT CHECK(status IN ('ONHAND', 'DEPLOYED', 'TRANSFER', 'MISSING')) NOT NULL,
    store_code_name TEXT,
    longitude REAL,
    latitude REAL,
    date_deployed DATE,
    pullout_date DATE,
    remarks TEXT CHECK(remarks IN ('NEW STORE', 'TEMPORARY', 'PERMANENT', 'FOR TESTING')),
    person_in_charge TEXT
);

CREATE TABLE device_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    store_code_name TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(device_id) REFERENCES devices(id) ON DELETE CASCADE
);