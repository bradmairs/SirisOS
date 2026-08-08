abstract final class ApiConfig {
  static const _configuredBaseUrl = String.fromEnvironment(
    'SIRISOS_API_URL',
    defaultValue: '',
  );

  static String get baseUrl {
    if (_configuredBaseUrl.isNotEmpty) return _configuredBaseUrl;
    final origin = Uri.base.origin;
    return origin == 'null' ? '' : origin;
  }
}
