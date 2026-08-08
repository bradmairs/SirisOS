import 'package:flutter/material.dart';

import '../services/knowledge_service.dart';

class KnowledgePanel extends StatefulWidget {
  const KnowledgePanel({super.key});

  @override
  State<KnowledgePanel> createState() => _KnowledgePanelState();
}

class _KnowledgePanelState extends State<KnowledgePanel> {
  final _service = KnowledgeService();
  late Future<KnowledgeOverview> _overview;

  @override
  void initState() {
    super.initState();
    _overview = _service.overview();
  }

  void _refresh() => setState(() => _overview = _service.overview());

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: FutureBuilder<KnowledgeOverview>(
          future: _overview,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snapshot.hasError) {
              return _MessageState(
                icon: Icons.menu_book_outlined,
                title: 'Knowledge unavailable',
                subtitle: 'Unable to read the vault right now.',
                onRefresh: _refresh,
              );
            }
            final data = snapshot.requireData;
            if (!data.available) {
              return _MessageState(
                icon: Icons.menu_book_outlined,
                title: 'Knowledge vault not mounted',
                subtitle: 'Configure your Markdown vault to activate this widget.',
                onRefresh: _refresh,
              );
            }

            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(Icons.menu_book_rounded),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Knowledge', style: Theme.of(context).textTheme.titleMedium),
                          Text('${data.noteCount} notes · ${data.vaultName}', style: Theme.of(context).textTheme.bodySmall),
                        ],
                      ),
                    ),
                    IconButton(
                      tooltip: 'Refresh Knowledge',
                      onPressed: _refresh,
                      icon: const Icon(Icons.refresh_rounded),
                    ),
                  ],
                ),
                const SizedBox(height: 14),
                if (data.recent.isEmpty)
                  const Text('No Markdown notes found.')
                else ...[
                  Text('Recently updated', style: Theme.of(context).textTheme.labelLarge),
                  const SizedBox(height: 8),
                  for (final note in data.recent.take(3))
                    Padding(
                      padding: const EdgeInsets.only(bottom: 7),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Icon(note.isDailyNote ? Icons.today_rounded : Icons.description_outlined, size: 17),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(note.title, maxLines: 1, overflow: TextOverflow.ellipsis),
                                Text(note.path, maxLines: 1, overflow: TextOverflow.ellipsis, style: Theme.of(context).textTheme.bodySmall),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                ],
              ],
            );
          },
        ),
      ),
    );
  }
}

class _MessageState extends StatelessWidget {
  const _MessageState({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onRefresh,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onRefresh;

  @override
  Widget build(BuildContext context) => Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, size: 34),
          const SizedBox(height: 10),
          Text(title, textAlign: TextAlign.center, style: Theme.of(context).textTheme.titleSmall),
          const SizedBox(height: 5),
          Text(subtitle, textAlign: TextAlign.center, style: Theme.of(context).textTheme.bodySmall),
          const SizedBox(height: 10),
          IconButton(onPressed: onRefresh, tooltip: 'Retry', icon: const Icon(Icons.refresh_rounded)),
        ],
      );
}
