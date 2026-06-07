const DH = { p: null, g: null, priv: null };

// base^exp mod m
function modPow(base, exp, mod) {
  let result = 1n;
  base %= mod;
  while (exp > 0n) {
    if (exp & 1n) result = (result * base) % mod;
    exp >>= 1n;
    base = (base * base) % mod;
  }
  return result;
}

// Generate a random BigInt
function randBig(bits_length) {
  const bytes = new Uint8Array(bits_length / 8);
  crypto.getRandomValues(bytes);
  let hex = "";
  for (const b of bytes) hex += b.toString(16).padStart(2, "0");
  return BigInt("0x" + hex);
}

// Minimal big-endian encoding, identical to Python int.to_bytes(ceil(bits/8))
function bigToBytes(b) {
  let hex = b.toString(16);
  if (hex.length % 2) hex = "0" + hex;
  const out = new Uint8Array(hex.length / 2);
  for (let i = 0; i < out.length; i++)
    out[i] = parseInt(hex.substr(i * 2, 2), 16);
  return out;
}

// Encode a byte array to a base64 string
function bytesToB64(bytes) {
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin);
}

// Decode a base64 string back into a byte array
function b64ToBytes(s) {
  const bin = atob(s);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

// Fetch the DH parameters (p, g) and all public keys
async function fetchKeys() {
  const res = await fetch("/keys");
  const data = await res.json();
  DH.p = BigInt(data.p);
  DH.g = BigInt(data.g);
  return data.keys;
}

// Load our private key from localStorage (or create one) and publish the
// matching public key to the server
async function ensureKeypair() {
  const stored = localStorage.getItem("dh_priv_" + ME);
  if (stored) {
    DH.priv = BigInt(stored);
  } else {
    DH.priv = randBig(256);
    localStorage.setItem("dh_priv_" + ME, DH.priv.toString());
  }

  if (DH.p === null) await fetchKeys();

  const pub = modPow(DH.g, DH.priv, DH.p);
  await fetch("/keys", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: ME, public_key: pub.toString() }),
  });
}

// Derive the shared AES-CBC key with a peer: sha256(otherPub^myPriv mod p)[:16]
async function sharedAesKey(otherPubStr) {
  const shared = modPow(BigInt(otherPubStr), DH.priv, DH.p);
  const digest = await crypto.subtle.digest("SHA-256", bigToBytes(shared));
  const keyBytes = new Uint8Array(digest).slice(0, 16);

  return crypto.subtle.importKey("raw", keyBytes, { name: "AES-CBC" }, false, [
    "encrypt",
    "decrypt",
  ]);
}

// Returns base64(iv[16] || AES-CBC ciphertext)
async function encryptMessage(otherPubStr, text) {
  const key = await sharedAesKey(otherPubStr);
  const iv = crypto.getRandomValues(new Uint8Array(16));
  const ct = new Uint8Array(
    await crypto.subtle.encrypt(
      { name: "AES-CBC", iv },
      key,
      new TextEncoder().encode(text),
    ),
  );

  const out = new Uint8Array(iv.length + ct.length);
  out.set(iv);
  out.set(ct, iv.length);

  return bytesToB64(out);
}

// Decrypt base64(iv[16] || ciphertext)
async function decryptMessage(otherPubStr, b64) {
  const key = await sharedAesKey(otherPubStr);
  const raw = b64ToBytes(b64);
  const iv = raw.slice(0, 16);
  const ct = raw.slice(16);
  const pt = await crypto.subtle.decrypt({ name: "AES-CBC", iv }, key, ct);

  return new TextDecoder().decode(pt);
}
