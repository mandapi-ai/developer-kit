import type { WireRequest } from '../types.js';
import { bodyJson, rubyQuote, staticHeaders, validateEnv } from './shared.js';

export function renderRuby(request: WireRequest): string {
  validateEnv(request);
  const headers = staticHeaders(request).map(([name, value]) => `request[${rubyQuote(name)}] = ${rubyQuote(value)}`).join('\n');
  return `# encoding: UTF-8
require 'net/http'
require 'uri'

api_key = ENV.fetch(${rubyQuote(request.auth.env)})
raise ${rubyQuote('Set ' + request.auth.env + ' before running this example.')} if api_key.empty?
base_override = ENV['MANDAPI_BASE_URL']
url = base_override && !base_override.empty? ? base_override.sub(%r{/+$}, '').sub(%r{/v1$}, '') + ${rubyQuote(request.path)} : ${rubyQuote(request.url)}
uri = URI(url)
request = Net::HTTPGenericRequest.new(${rubyQuote(request.method)}, true, true, uri)
${headers}
request[${rubyQuote(request.auth.header)}] = ${rubyQuote(request.auth.prefix)} + api_key
request.body = ${rubyQuote(bodyJson(request))}
response = Net::HTTP.start(uri.host, uri.port, use_ssl: uri.scheme == 'https', open_timeout: 30, read_timeout: 300) do |http|
  http.request(request)
end
raise "HTTP #{response.code}: #{response.body}" unless response.code.to_i.between?(200, 299)
puts response.body
`;
}
