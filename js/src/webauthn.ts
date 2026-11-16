/**
 * Passkey helpers. allauth sends WebAuthn options as JSON with base64url
 * strings and accepts the credential back as JSON. Modern browsers convert
 * natively (`parseCreationOptionsFromJSON`, `toJSON`); the fallbacks below
 * cover older ones.
 */

type Json = Record<string, any>;

function b64urlToBuffer(value: string): ArrayBuffer {
  const b64 = value.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(value.length / 4) * 4, "=");
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes.buffer;
}

function bufferToB64url(value: ArrayBuffer): string {
  const bytes = new Uint8Array(value);
  let bin = "";
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function decodeDescriptors(list?: Json[]) {
  return list?.map((c) => ({ ...c, id: b64urlToBuffer(c.id) }));
}

function publicKeyOf(options: Json): Json {
  return options.publicKey ?? options;
}

function credentialToJSON(cred: PublicKeyCredential): Json {
  if (typeof (cred as any).toJSON === "function") return (cred as any).toJSON();
  const r = cred.response as any;
  const response: Json = { clientDataJSON: bufferToB64url(r.clientDataJSON) };
  if (r.attestationObject) {
    response.attestationObject = bufferToB64url(r.attestationObject);
    response.transports = r.getTransports?.() ?? [];
  } else {
    response.authenticatorData = bufferToB64url(r.authenticatorData);
    response.signature = bufferToB64url(r.signature);
    if (r.userHandle) response.userHandle = bufferToB64url(r.userHandle);
  }
  return {
    id: cred.id,
    rawId: bufferToB64url(cred.rawId),
    type: cred.type,
    authenticatorAttachment: (cred as any).authenticatorAttachment ?? undefined,
    clientExtensionResults: cred.getClientExtensionResults(),
    response,
  };
}

export function passkeysSupported(): boolean {
  return typeof window !== "undefined" && typeof window.PublicKeyCredential === "function";
}

/** Runs the browser's "create a passkey" prompt with allauth's `creation_options`. */
export async function createCredential(creationOptions: Json): Promise<Json> {
  const json = publicKeyOf(creationOptions);
  const PKC = PublicKeyCredential as any;
  const publicKey = typeof PKC.parseCreationOptionsFromJSON === "function"
    ? PKC.parseCreationOptionsFromJSON(json)
    : {
        ...json,
        challenge: b64urlToBuffer(json.challenge),
        user: { ...json.user, id: b64urlToBuffer(json.user.id) },
        excludeCredentials: decodeDescriptors(json.excludeCredentials),
      };
  const cred = (await navigator.credentials.create({ publicKey })) as PublicKeyCredential | null;
  if (!cred) throw new Error("Passkey creation was cancelled.");
  return credentialToJSON(cred);
}

/** Runs the browser's "use a passkey" prompt with allauth's `request_options`. */
export async function getCredential(requestOptions: Json): Promise<Json> {
  const json = publicKeyOf(requestOptions);
  const PKC = PublicKeyCredential as any;
  const publicKey = typeof PKC.parseRequestOptionsFromJSON === "function"
    ? PKC.parseRequestOptionsFromJSON(json)
    : { ...json, challenge: b64urlToBuffer(json.challenge), allowCredentials: decodeDescriptors(json.allowCredentials) };
  const cred = (await navigator.credentials.get({ publicKey })) as PublicKeyCredential | null;
  if (!cred) throw new Error("Passkey sign-in was cancelled.");
  return credentialToJSON(cred);
}
