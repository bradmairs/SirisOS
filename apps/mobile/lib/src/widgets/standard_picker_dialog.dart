import 'package:flutter/material.dart';

import '../services/engineering_standards_service.dart';

/// Shows a search/filter dialog over the private standards library and
/// resolves to the document the user picked, or null if cancelled.
/// Shared by any flow that needs to attach/cite an exact standards
/// revision (Project relationships, saved calculations, ...).
Future<EngineeringStandardDocument?> showStandardPickerDialog(
  BuildContext context, {
  required EngineeringStandardsService service,
  String title = 'Choose a standard',
}) {
  return showDialog<EngineeringStandardDocument>(
    context: context,
    builder: (_) => _StandardPickerDialog(service: service, title: title),
  );
}

class _StandardPickerDialog extends StatefulWidget {
  const _StandardPickerDialog({required this.service, required this.title});
  final EngineeringStandardsService service;
  final String title;

  @override
  State<_StandardPickerDialog> createState() => _StandardPickerDialogState();
}

class _StandardPickerDialogState extends State<_StandardPickerDialog> {
  final _search = TextEditingController();
  late Future<List<EngineeringStandardSearchHit>> _results;

  @override
  void initState() {
    super.initState();
    _results = widget.service.search();
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  void _runSearch() => setState(() {
        _results = widget.service.search(query: _search.text.trim());
      });

  List<EngineeringStandardDocument> _uniqueDocuments(
    List<EngineeringStandardSearchHit> hits,
  ) {
    final byId = <String, EngineeringStandardDocument>{};
    for (final hit in hits) {
      if (hit.document.active) byId.putIfAbsent(hit.document.id, () => hit.document);
    }
    return byId.values.toList(growable: false);
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(widget.title),
      content: SizedBox(
        width: 620,
        height: 500,
        child: Column(
          children: [
            TextField(
              controller: _search,
              onSubmitted: (_) => _runSearch(),
              decoration: InputDecoration(
                labelText: 'Search standards',
                prefixIcon: const Icon(Icons.search_rounded),
                suffixIcon: IconButton(
                  onPressed: _runSearch,
                  icon: const Icon(Icons.arrow_forward_rounded),
                ),
                border: const OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 12),
            Expanded(
              child: FutureBuilder<List<EngineeringStandardSearchHit>>(
                future: _results,
                builder: (context, snapshot) {
                  if (snapshot.connectionState == ConnectionState.waiting) {
                    return const Center(child: CircularProgressIndicator());
                  }
                  if (snapshot.hasError) {
                    return Center(child: Text('Standards unavailable: ${snapshot.error}'));
                  }
                  final documents = _uniqueDocuments(snapshot.data ?? const []);
                  if (documents.isEmpty) {
                    return const Center(child: Text('No active matching standards found.'));
                  }
                  return ListView.separated(
                    itemCount: documents.length,
                    separatorBuilder: (_, __) => const Divider(height: 1),
                    itemBuilder: (context, index) {
                      final document = documents[index];
                      return ListTile(
                        leading: const Icon(Icons.library_books_rounded),
                        title: Text(standardIdentity(document)),
                        subtitle: Text(
                          '${document.authority} · exact document revision ${document.revision}',
                        ),
                        onTap: () => Navigator.pop(context, document),
                      );
                    },
                  );
                },
              ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
      ],
    );
  }
}

/// Human-readable identity for a standard: reference/title, edition, and
/// library revision when it's been replaced more than once.
String standardIdentity(EngineeringStandardDocument document) {
  final parts = <String>[
    if (document.reference?.trim().isNotEmpty == true) document.reference!.trim() else document.title,
    if (document.edition?.trim().isNotEmpty == true) document.edition!.trim(),
    if (document.revision > 1) 'library rev. ${document.revision}',
  ];
  return parts.join(' · ');
}
