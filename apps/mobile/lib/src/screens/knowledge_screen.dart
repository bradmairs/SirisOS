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
  late Future<KnowledgeBrowse> _browse;
  Future<List<KnowledgeNoteSummary>>? _searchResults;
  String? _folderFilter;
  String? _tagFilter;

  @override
  void initState() {
    super.initState();
    _overview = _service.overview();
    _browse = _service.browse();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  void _refresh() => setState(() {
        _overview = _service.overview();
        _browse = _service.browse();
        _searchResults = null;
        _searchController.clear();
        _folderFilter = null;
        _tagFilter = null;
      });

  void _runFilteredSearch() {
    setState(() {
      _searchResults = _service.search(
        _searchController.text.trim(),
        folder: _folderFilter,
        tag: _tagFilter,
      );
    });
  }

  void _clearFilters() {
    setState(() {
      _folderFilter = null;
      _tagFilter = null;
      if (_searchController.text.trim().isEmpty) {
        _searchResults = null;
      } else {
        _searchResults = _service.search(_searchController.text.trim());
      }
    });
  }

  Future<void> _openWikiTarget(String target, String sourcePath) async {
    try {
      final result = await _service.resolveLink(target, sourcePath: sourcePath);
      if (!mounted) return;
      if (result.resolved && result.note != null) {
        await _openNote(result.note!);
        return;
      }
      if (result.ambiguous && result.candidates.isNotEmpty) {
        final selected = await showDialog<KnowledgeNoteSummary>(
          context: context,
          builder: (context) => AlertDialog(
            title: Text('Choose “$target”'),
            content: SizedBox(
              width: 520,
              child: ListView(
                shrinkWrap: true,
                children: [
                  const Text('More than one note matches this wikilink.'),
                  const SizedBox(height: 12),
                  for (final candidate in result.candidates)
                    ListTile(
                      leading: const Icon(Icons.description_outlined),
                      title: Text(candidate.title),
                      subtitle: Text(candidate.path),
                      onTap: () => Navigator.pop(context, candidate),
                    ),
                ],
              ),
            ),
            actions: [
              TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
            ],
          ),
        );
        if (selected != null && mounted) await _openNote(selected);
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('No note resolves [[${result.target}]].')),
      );
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Unable to resolve link: $error')),
      );
    }
  }

  Future<void> _openNote(KnowledgeNoteSummary summary) async {
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => Dialog(
        child: SizedBox(
          width: 860,
          height: 760,
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
                          onPressed: () => Navigator.pop(dialogContext),
                          icon: const Icon(Icons.close_rounded),
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(note.path, style: Theme.of(context).textTheme.bodySmall),
                    if (note.tags.isNotEmpty) ...[
                      const SizedBox(height: 10),
                      Wrap(
                        spacing: 6,
                        runSpacing: 6,
                        children: note.tags
                            .map(
                              (tag) => ActionChip(
                                label: Text('#$tag'),
                                onPressed: () {
                                  Navigator.pop(dialogContext);
                                  setState(() {
                                    _tagFilter = tag;
                                    _folderFilter = null;
                                    _searchResults = _service.search('', tag: tag);
                                  });
                                },
                              ),
                            )
                            .toList(growable: false),
                      ),
                    ],
                    if (note.wikilinks.isNotEmpty) ...[
                      const SizedBox(height: 12),
                      Text('Links', style: Theme.of(context).textTheme.titleSmall),
                      const SizedBox(height: 6),
                      Wrap(
                        spacing: 6,
                        runSpacing: 6,
                        children: note.wikilinks
                            .map(
                              (link) => ActionChip(
                                avatar: const Icon(Icons.arrow_outward_rounded, size: 16),
                                label: Text(link),
                                onPressed: () {
                                  Navigator.pop(dialogContext);
                                  Future<void>.delayed(Duration.zero, () => _openWikiTarget(link, note.path));
                                },
                              ),
                            )
                            .toList(growable: false),
                      ),
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
                    const Divider(),
                    FutureBuilder<List<KnowledgeNoteSummary>>(
                      future: _service.backlinks(note.path),
                      builder: (context, backlinks) {
                        if (backlinks.connectionState == ConnectionState.waiting) {
                          return const LinearProgressIndicator();
                        }
                        if (backlinks.hasError) {
                          return Text('Backlinks unavailable: ${backlinks.error}', style: Theme.of(context).textTheme.bodySmall);
                        }
                        final values = backlinks.data ?? const [];
                        if (values.isEmpty) {
                          return Text('No backlinks', style: Theme.of(context).textTheme.bodySmall);
                        }
                        return Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('Backlinks · ${values.length}', style: Theme.of(context).textTheme.titleSmall),
                            const SizedBox(height: 6),
                            SizedBox(
                              height: 42,
                              child: ListView.separated(
                                scrollDirection: Axis.horizontal,
                                itemCount: values.length,
                                separatorBuilder: (_, __) => const SizedBox(width: 6),
                                itemBuilder: (_, index) {
                                  final backlink = values[index];
                                  return ActionChip(
                                    avatar: const Icon(Icons.subdirectory_arrow_left_rounded, size: 16),
                                    label: Text(backlink.title),
                                    onPressed: () {
                                      Navigator.pop(dialogContext);
                                      Future<void>.delayed(Duration.zero, () => _openNote(backlink));
                                    },
                                  );
                                },
                              ),
                            ),
                          ],
                        );
                      },
                    ),
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
                onSubmitted: (_) => _runFilteredSearch(),
                decoration: InputDecoration(
                  labelText: 'Search your vault',
                  hintText: 'Projects, standards, meeting notes, ideas…',
                  prefixIcon: const Icon(Icons.search_rounded),
                  suffixIcon: IconButton(onPressed: _runFilteredSearch, icon: const Icon(Icons.arrow_forward_rounded)),
                  border: const OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 14),
              FutureBuilder<KnowledgeBrowse>(
                future: _browse,
                builder: (context, browseSnapshot) {
                  if (!browseSnapshot.hasData) return const SizedBox.shrink();
                  final browse = browseSnapshot.requireData;
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      if (_folderFilter != null || _tagFilter != null) ...[
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: [
                            if (_folderFilter != null) Chip(label: Text('Folder: $_folderFilter')),
                            if (_tagFilter != null) Chip(label: Text('#$_tagFilter')),
                            ActionChip(label: const Text('Clear filters'), onPressed: _clearFilters),
                          ],
                        ),
                        const SizedBox(height: 10),
                      ],
                      ExpansionTile(
                        tilePadding: EdgeInsets.zero,
                        title: Text('Browse folders · ${browse.folders.length}'),
                        children: [
                          Align(
                            alignment: Alignment.centerLeft,
                            child: Wrap(
                              spacing: 8,
                              runSpacing: 8,
                              children: browse.folders
                                  .map(
                                    (folder) => ActionChip(
                                      avatar: const Icon(Icons.folder_outlined, size: 16),
                                      label: Text('${folder.path} (${folder.noteCount})'),
                                      onPressed: () {
                                        setState(() {
                                          _folderFilter = folder.path;
                                          _tagFilter = null;
                                          _searchResults = _service.search(_searchController.text.trim(), folder: folder.path);
                                        });
                                      },
                                    ),
                                  )
                                  .toList(growable: false),
                            ),
                          ),
                        ],
                      ),
                      ExpansionTile(
                        tilePadding: EdgeInsets.zero,
                        title: Text('Browse tags · ${browse.tags.length}'),
                        children: [
                          Align(
                            alignment: Alignment.centerLeft,
                            child: Wrap(
                              spacing: 8,
                              runSpacing: 8,
                              children: browse.tags
                                  .map(
                                    (tag) => ActionChip(
                                      label: Text('#${tag.tag} (${tag.noteCount})'),
                                      onPressed: () {
                                        setState(() {
                                          _tagFilter = tag.tag;
                                          _folderFilter = null;
                                          _searchResults = _service.search(_searchController.text.trim(), tag: tag.tag);
                                        });
                                      },
                                    ),
                                  )
                                  .toList(growable: false),
                            ),
                          ),
                        ],
                      ),
                    ],
                  );
                },
              ),
              const SizedBox(height: 16),
              if (_searchResults != null)
                FutureBuilder<List<KnowledgeNoteSummary>>(
                  future: _searchResults,
                  builder: (context, results) {
                    if (results.connectionState == ConnectionState.waiting) {
                      return const Center(child: Padding(padding: EdgeInsets.all(24), child: CircularProgressIndicator()));
                    }
                    if (results.hasError) return Text('Search failed: ${results.error}');
                    final hits = results.data ?? const [];
                    return _NoteSection(title: 'Results', notes: hits, onOpen: _openNote);
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
                  trailing: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      if (note.wikilinks.isNotEmpty) Text('${note.wikilinks.length} ↗'),
                      const SizedBox(width: 6),
                      const Icon(Icons.chevron_right_rounded),
                    ],
                  ),
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
