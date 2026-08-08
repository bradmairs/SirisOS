abstract final class DisplayConfig {
  static const hostName = String.fromEnvironment(
    'SIRISOS_HOST_DISPLAY_NAME',
    defaultValue: 'Linux Server',
  );

  static const upsName = String.fromEnvironment(
    'SIRISOS_UPS_DISPLAY_NAME',
    defaultValue: 'Server UPS',
  );

  static String hostLabel(String? canonicalHostname) {
    final alias = hostName.trim();
    if (alias.isNotEmpty) return alias;
    final canonical = canonicalHostname?.trim();
    return canonical == null || canonical.isEmpty ? 'SirisOS host' : canonical;
  }

  static String upsLabel({String? description, String? canonicalName}) {
    final alias = upsName.trim();
    if (alias.isNotEmpty) return alias;
    final descriptionValue = description?.trim();
    if (descriptionValue != null &&
        descriptionValue.isNotEmpty &&
        descriptionValue.toLowerCase() != 'description unavailable') {
      return descriptionValue;
    }
    final canonical = canonicalName?.trim();
    return canonical == null || canonical.isEmpty ? 'UPS' : canonical;
  }
}
