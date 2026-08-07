class SirisConnectorConfiguration {
  const SirisConnectorConfiguration({
    required this.connectorId,
    this.enabled = true,
    this.endpoint,
    this.credentialRef,
    this.options = const <String, String>{},
  });

  final String connectorId;
  final bool enabled;
  final String? endpoint;

  /// Opaque reference to credentials managed outside Flutter client storage.
  final String? credentialRef;

  /// Non-secret connector options only.
  final Map<String, String> options;

  SirisConnectorConfiguration copyWith({
    bool? enabled,
    String? endpoint,
    String? credentialRef,
    Map<String, String>? options,
  }) =>
      SirisConnectorConfiguration(
        connectorId: connectorId,
        enabled: enabled ?? this.enabled,
        endpoint: endpoint ?? this.endpoint,
        credentialRef: credentialRef ?? this.credentialRef,
        options: options ?? this.options,
      );
}
