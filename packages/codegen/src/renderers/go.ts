import type { WireRequest } from '../types.js';
import { bodyJson, quote, staticHeaders, validateEnv } from './shared.js';

export function renderGo(request: WireRequest): string {
  validateEnv(request);
  const headers = staticHeaders(request).map(([name, value]) => `    req.Header.Set(${quote(name)}, ${quote(value)})`).join('\n');
  return `package main

import (
    "fmt"
    "io"
    "net/http"
    "os"
    "strings"
    "time"
)

func main() {
    apiKey := os.Getenv(${quote(request.auth.env)})
    if apiKey == "" { panic(${quote('Set ' + request.auth.env + ' before running this example.')}) }
    url := ${quote(request.url)}
    if baseOverride := os.Getenv("MANDAPI_BASE_URL"); baseOverride != "" {
        url = strings.TrimSuffix(strings.TrimRight(baseOverride, "/"), "/v1") + ${quote(request.path)}
    }
    payload := ${quote(bodyJson(request))}
    req, err := http.NewRequest(${quote(request.method)}, url, strings.NewReader(payload))
    if err != nil { panic(err) }
${headers}
    req.Header.Set(${quote(request.auth.header)}, ${quote(request.auth.prefix)} + apiKey)
    client := &http.Client{Timeout: 5 * time.Minute}
    response, err := client.Do(req)
    if err != nil { panic(err) }
    defer response.Body.Close()
    result, err := io.ReadAll(response.Body)
    if err != nil { panic(err) }
    if response.StatusCode < 200 || response.StatusCode >= 300 {
        panic(fmt.Sprintf("HTTP %d: %s", response.StatusCode, result))
    }
    fmt.Println(string(result))
}
`;
}
