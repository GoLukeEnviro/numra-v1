import assert from "node:assert/strict";
import { test } from "node:test";

import { NOT_READY_BODY, RENDER_FAILED_BODY, sendFailure } from "../errors.js";

function fakeResponse() {
  const sent = {};
  const res = {
    status(code) {
      sent.status = code;
      return res;
    },
    json(body) {
      sent.body = body;
      return res;
    },
  };
  return { res, sent };
}

const INTERNAL_ERROR = new Error(
  "browserType.launch: Executable doesn't exist at /root/.cache/ms-playwright/chromium-1234/chrome-linux/chrome",
);

for (const [name, status, body] of [
  ["render failure", 500, RENDER_FAILED_BODY],
  ["readiness failure", 503, NOT_READY_BODY],
]) {
  test(`${name} sends only the generic body and logs the error`, () => {
    const { res, sent } = fakeResponse();
    const logged = [];

    sendFailure(res, status, body, name, INTERNAL_ERROR, (...args) => logged.push(args));

    assert.equal(sent.status, status);
    assert.deepEqual(sent.body, body);
    const wire = JSON.stringify(sent.body);
    assert.doesNotMatch(wire, /ms-playwright|\/root\/|Error:|at \S+ \(/);
    assert.equal(logged.length, 1);
    assert.equal(logged[0][1], INTERNAL_ERROR);
  });
}
