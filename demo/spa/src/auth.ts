import { createAuthClient } from "dj-rest-jwt-client";

/**
 * The one auth client for the app. A browser SPA uses the default cookie
 * transport: tokens live in httpOnly cookies this code can never read.
 *
 * A React Native / Capacitor app would instead use
 *   createAuthClient({ baseUrl: "https://api.example.com/api/auth/v1",
 *                      transport: "header", tokenStore: secureStore })
 */
export const auth = createAuthClient({ baseUrl: "/api/auth/v1" });
