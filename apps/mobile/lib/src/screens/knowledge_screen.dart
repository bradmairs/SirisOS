import 'package:flutter/material.dart';

import '../services/knowledge_service.dart';

class KnowledgeScreen extends StatefulWidget {
  const KnowledgeScreen({super.key});

  @override
  State<KnowledgeScreen> createState() => _KnowledgeScreenState();
}

class _KnowledgeScreenState extends State<KnowledgeScreen> {
  final _service = KnowledgeService();
  final _searchController = TextEditingController();
  late Future<KnowledgeOverview> _overview;
  Future<List<KnowledgeNoteSummary>>? _searchResults;

  @override
  void initState() {
    super.initState();
    _overview = _service.overview();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  void _refresh() => setState(() {
        _overview = _service.overview();
        _searchResults = null;
        _searchController.clear();
      });

  void _search() {
    final query = _searchController.text.trim();
    if (query.isEmpty) {
      setState(() => _searchResults = null);
      return;
    }
    setState(() => _searchResults = _service.search(query));
  }

  Future<void> _openNote(KnowledgeNoteSummary summary) async {
    await showDialog<void>(
      context: context,
      builder: (context) => Dialog(
        child: SizedBox(
          width: 820,
          height: 720,
          child: FutureBuilder<KnowledgeNote>(
            future: _service.note(summary.path),
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return const Center(child: CircularProgressIndicator());
              }
              if (snapshot.hasError) {
                return Padding(
                  padding: const EdgeInsets.all(24),
                  child: Text('Unable to open note: ${snapshot.error}'),
                );
              }
              final note = snapshot.requireData;
              return Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(child: Text(note.title, style: Theme.of(context).textTheme.headlineSmall)),
                        IconButton(
                          tooltip: 'Close',
                          onPressed: () => Navigator.pop(context),
                          icon: const Icon(Icons.close_rounded),
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(note.path, style: Theme.of(context).textTheme.bodySmall),
                    if (note.tags.isNotEmpty) ...[
                      const SizedBox(height: 10),
                      Wrap(spacing: 6, runSpacing: 6, children: note.tags.map((tag) => Chip(label: Text('#$tag'))).toList()),
                    ],
                    const SizedBox(height: 12),
                    const Divider(),
                    const SizedBox(height: 8),
                    Expanded(
                      child: SelectionArea(
                        child: SingleChildScrollView(
                          child: Text(note.content, style: const TextStyle(fontFamily: 'monospace', height: 1.45)),
                        ),
                      ),
                    ),
                    if (note.wikilinks.isNotEmpty) ...[
                      const Divider(),
                      Text('Links: ${note.wikilinks.join(' · ')}', style: Theme.of(context).textTheme.bodySmall),
                    ],
                  ],
                ),
              );
            },
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: FutureBuilder<KnowledgeOverview>(
        future: _overview,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return _KnowledgeUnavailable(message: snapshot.error.toString(), onRetry: _refresh);
          }
          final data = snapshot.requireData;
          if (!data.available) {
            return _KnowledgeUnavailable(
              message: 'No knowledge vault is mounted yet. Configure SIRISOS_KNOWLEDGE_HOST_PATH and rebuild SirisOS.',
              onRetry: _refresh,
            );
          }
          return ListView(
            padding: const EdgeInsets.all(24),
            children: [
              Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Knowledge', style: Theme.of(context).textTheme.headlineMedium),
                        const SizedBox(height: 4),
                        Text('${data.vaultName} · ${data.noteCount} Markdown notes'),
                      ],
                    ),
                  ),
                  IconButton.filledTonal(onPressed: _refresh, tooltip: 'Refresh vault', icon: const Icon(Icons.refresh_rounded)),
                ],
              ),
              const SizedBox(height: 20),
              TextField(
                controller: _searchController,
                onSubmitted: (_) => _search(),
                decoration: InputDecoration(
                  labelText: 'Search your vault',
                  hintText: 'Projects, standards, meeting notes, ideas…',
                  prefixIcon: const Icon(Icons.search_rounded),
                  suffixIcon: IconButton(onPressed: _search, icon: const Icon(Icons.arrow_forward_rounded)),
                  border: const OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 20),
              if (_searchResults != null)
                FutureBuilder<List<KnowledgeNoteSummary>>(
                  future: _searchResults,
                  builder: (context, results) {
                    if (results.connectionState == ConnectionState.waiting) {
                      return const Center(child: Padding(padding: EdgeInsets.all(24), child: CircularProgressIndicator()));
                    }
                    if (results.hasError) return Text('Search failed: ${results.error}');
                    final hits = results.data ?? const [];
                    return _NoteSection(title: 'Search results', notes: hits, onOpen: _openNote);
                  },
                )
              else ...[
                if (data.daily.isNotEmpty) ...[
                  _NoteSection(title: 'Daily notes', notes: data.daily, onOpen: _openNote),
                  const SizedBox(height: 20),
                ],
                _NoteSection(title: 'Recent notes', notes: data.recent, onOpen: _openNote),
              ],
            ],
          );
        },
      ),
    );
  }
}

class _NoteSection extends StatelessWidget {
  const _NoteSection({required this.title, required this.notes, required this.onOpen});
  final String title;
  final List<KnowledgeNoteSummary> notes;
  final Future<void> Function(KnowledgeNoteSummary note) onOpen;

  @override
  Widget build(BuildContext context) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 10),
          if (notes.isEmpty)
            const Card(child: Padding(padding: EdgeInsets.all(18), child: Text('No notes found.')))
          else
            for (final note in notes)
              Card(
                margin: const EdgeInsets.only(bottom: 10),
                child: ListTile(
                  leading: Icon(note.isDailyNote ? Icons.today_rounded : Icons.description_outlined),
                  title: Text(note.title),
                  subtitle: Text(note.path, maxLines: 1, overflow: TextOverflow.ellipsis),
                  trailing: const Icon(Icons.chevron_right_rounded),
                  onTap: () => onOpen(note),
                ),
              ),
        ],
      );
}

class _KnowledgeUnavailable extends StatelessWidget {
  const _KnowledgeUnavailable({required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.menu_book_rounded, size: 58),
              const SizedBox(height: 16),
              Text('Knowledge vault unavailable', style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 10),
              Text(message, textAlign: TextAlign.center),
              const SizedBox(height: 18),
              FilledButton.icon(onPressed: onRetry, icon: const Icon(Icons.refresh_rounded), label: const Text('Try again')),
            ],
          ),
        ),
      );
}
