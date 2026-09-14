import * as SecureStore from "expo-secure-store";

import type { TokenStore } from "../api/auth-client";

const SESSION_KEY = "avenyth.native.session";

export const secureTokenStore: TokenStore = {
  get: () => SecureStore.getItemAsync(SESSION_KEY),
  set: (value) =>
    SecureStore.setItemAsync(SESSION_KEY, value, {
      keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
    }),
  delete: () => SecureStore.deleteItemAsync(SESSION_KEY),
};
