import type { WireRequest } from '../types.js';
import { bodyJson, quote, staticHeaders, validateEnv } from './shared.js';

export function renderCSharp(request: WireRequest): string {
  validateEnv(request);
  const headers = staticHeaders(request).map(([name, value]) => `if (!request.Headers.TryAddWithoutValidation(${quote(name)}, ${quote(value)}))
    request.Content.Headers.TryAddWithoutValidation(${quote(name)}, ${quote(value)});`).join('\n');
  return `using System;
using System.Net.Http;
using System.Text;

var apiKey = Environment.GetEnvironmentVariable(${quote(request.auth.env)});
if (string.IsNullOrEmpty(apiKey)) throw new InvalidOperationException(${quote('Set ' + request.auth.env + ' before running this example.')});
var baseOverride = Environment.GetEnvironmentVariable("MANDAPI_BASE_URL");
var baseRoot = baseOverride?.TrimEnd('/');
if (baseRoot?.EndsWith("/v1", StringComparison.Ordinal) == true)
    baseRoot = baseRoot.Substring(0, baseRoot.Length - 3);
var url = !string.IsNullOrEmpty(baseRoot)
    ? baseRoot + ${quote(request.path)}
    : ${quote(request.url)};
var payload = ${quote(bodyJson(request))};
using var client = new HttpClient { Timeout = TimeSpan.FromMinutes(5) };
using var request = new HttpRequestMessage(new HttpMethod(${quote(request.method)}), url);
request.Content = new ByteArrayContent(Encoding.UTF8.GetBytes(payload));
${headers}
request.Headers.TryAddWithoutValidation(${quote(request.auth.header)}, ${quote(request.auth.prefix)} + apiKey);
using var response = await client.SendAsync(request);
var result = await response.Content.ReadAsStringAsync();
if (!response.IsSuccessStatusCode)
    throw new HttpRequestException("HTTP " + (int)response.StatusCode + ": " + result);
Console.WriteLine(result);
`;
}
