import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../config/knowledge_config.dart';
import 'knowledge_screen.dart';

class KnowledgeHubScreen extends StatelessWidget {
  const KnowledgeHubScreen({super.key});

  Future<void> _openObsidian(BuildContext context) async {
    final uri = Uri.tryParse(KnowledgeConfig.obsidianUrl.trim());
    if (uri == null || !await launchUrl(uri, mode: LaunchMode.platformDefault)) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Unable to open the configured Obsidian/Selkies URL.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!KnowledgeConfig.canLaunchObsidian) return const KnowledgeScreen();

    return Column(
      children: [
        SafeArea(
          bottom: false,
          child: Container(
            width: double.infinity,
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 12),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surface,
              border: Border(
                bottom: BorderSide(color: Theme.of(context).dividerColor),
              ),
            ),
            child: Row(
              children: [
                const Icon(Icons.auto_stories_rounded),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Obsidian', style: Theme.of(context).textTheme.titleMedium),
                      Text(
                        'Open the configured Selkies/Obsidian workspace.',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              color: Theme.of(context).colorScheme.onSurfaceVariant,
                            ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 12),
                FilledButton.tonalIcon(
                  onPressed: () => _openObsidian(context),
                  icon: const Icon(Icons.open_in_new_rounded),
                  label: const Text('Open'),
                ),
              ],
            ),
          ),
        ),
        const Expanded(child: KnowledgeScreen()),
      ],
    );
  }
}
