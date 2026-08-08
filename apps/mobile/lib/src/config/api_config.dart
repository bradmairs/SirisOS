abstract final class ApiConfig {
  static const baseUrl = String.fromEnvironment(
    'SIRISOS_API_URL',
    defaultValue: '',
  );
}
