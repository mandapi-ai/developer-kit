import type { WireRequest } from '../types.js';
import { bodyJson, javaQuote, staticHeaders, validateEnv } from './shared.js';

export function renderJava(request: WireRequest): string {
  validateEnv(request);
  const headers = staticHeaders(request).map(([name, value]) => `            .header(${javaQuote(name)}, ${javaQuote(value)})`).join('\n');
  return `import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;

public class Main {
    public static void main(String[] args) throws Exception {
        String apiKey = System.getenv(${javaQuote(request.auth.env)});
        if (apiKey == null || apiKey.isEmpty()) throw new IllegalStateException(${javaQuote('Set ' + request.auth.env + ' before running this example.')});
        String baseOverride = System.getenv("MANDAPI_BASE_URL");
        String url = baseOverride != null && !baseOverride.isEmpty()
            ? baseOverride.replaceAll("/+$", "").replaceFirst("/v1$", "") + ${javaQuote(request.path)}
            : ${javaQuote(request.url)};
        String payload = ${javaQuote(bodyJson(request))};
        HttpRequest request = HttpRequest.newBuilder(URI.create(url))
            .timeout(Duration.ofMinutes(5))
${headers}
            .header(${javaQuote(request.auth.header)}, ${javaQuote(request.auth.prefix)} + apiKey)
            .method(${javaQuote(request.method)}, HttpRequest.BodyPublishers.ofString(payload, StandardCharsets.UTF_8))
            .build();
        HttpClient client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(30)).build();
        HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
        if (response.statusCode() < 200 || response.statusCode() >= 300) {
            throw new IllegalStateException("HTTP " + response.statusCode() + ": " + response.body());
        }
        System.out.println(response.body());
    }
}
`;
}
