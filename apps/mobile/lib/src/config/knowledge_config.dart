abstract final class KnowledgeConfig {
  static const obsidianUrl = String.fromEnvironment(
    'SIRISOS_OBSIDIAN_URL',
    defaultValue: '',
  );

  static bool get canLaunchObsidian => obsidianUrl.trim().isNotEmpty;
}
