class SirisSearchResult {
  const SirisSearchResult({
    required this.module,
    required this.title,
    required this.subtitle,
    required this.target,
    required this.referenceId,
  });

  factory SirisSearchResult.fromJson(Map<String, dynamic> json) => SirisSearchResult(
        module: json['module'] as String,
        title: json['title'] as String,
        subtitle: json['subtitle'] as String,
        target: json['target'] as String,
        referenceId: json['reference_id'] as String?,
      );

  final String module;
  final String title;
  final String subtitle;
  final String target;
  final String? referenceId;
}
