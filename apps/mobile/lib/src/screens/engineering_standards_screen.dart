import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../services/engineering_standards_service.dart';
import '../widgets/standard_page_dialog.dart';

class EngineeringStandardsScreen extends StatefulWidget {
  const EngineeringStandardsScreen({super.key});

  @override
  State<EngineeringStandardsScreen> createState() => _EngineeringStandardsScreenState();
}

class _EngineeringStandardsScreenState extends State<EngineeringStandardsScreen> {
  final _service = EngineeringStandardsService();
  final _search = TextEditingController();
  late Future<List<EngineeringStandardSearchHit>> _results;
  bool _includeArchived = false;

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  void _refresh() {
    _results = _service.search(
      query: _search.text.trim(),
      includeArchived: _includeArchived,
    );
  }

  void _runSearch() => setState(_refresh);

  Future<void> _showPage(EngineeringStandardSearchHit hit) async {
    final pageNumber = hit.page;
    if (pageNumber == null) return;
    await showStandardPageDialog(
      context,
      service: _service,
      documentId: hit.document.id,
      page: pageNumber,
    );
  }

  Future<void> _showUploadDialog({EngineeringStandardDocument? replacing}) async {
    final title = TextEditingController(text: replacing?.title ?? '');
    final authority = TextEditingController(text: replacing?.authority ?? '');
    final reference = TextEditingController(text: replacing?.reference ?? '');
    final edition = TextEditingController(text: replacing?.edition ?? '');
    PlatformFile? selected;
    bool uploading = false;
    String? error;

    try {
      await showDialog<void>(
        context: context,
        barrierDismissible: !uploading,
        builder: (dialogContext) => StatefulBuilder(
          builder: (context, setDialogState) => AlertDialog(
            title: Text(replacing == null ? 'Add licensed standard' : 'Replace with new revision'),
            content: SizedBox(
              width: 560,
              child: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      replacing == null
                          ? 'Upload a PDF you are entitled to store and use. SirisOS keeps it private and indexes it locally.'
                          : 'The existing revision will be archived, not overwritten. Existing citations will continue to resolve to that historical revision.',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                    const SizedBox(height: 16),
                    OutlinedButton.icon(
                      onPressed: uploading
                          ? null
                          : () async {
                              final result = await FilePicker.platform.pickFiles(
                                type: FileType.custom,
                                allowedExtensions: const ['pdf'],
                                withData: true,
                              );
                              if (result != null && result.files.isNotEmpty) {
                                setDialogState(() {
                                  selected = result.files.single;
                                  if (title.text.trim().isEmpty) {
                                    title.text = selected!.name.replaceFirst(
                                      RegExp(r'\.pdf$', caseSensitive: false),
                                      '',
                                    );
                                  }
                                  error = null;
                                });
                              }
                            },
                      icon: const Icon(Icons.picture_as_pdf_rounded),
                      label: Text(selected?.name ?? 'Choose PDF'),
                    ),
                    const SizedBox(height: 16),
                    TextField(
                      controller: title,
                      enabled: !uploading,
                      decoration: const InputDecoration(labelText: 'Title', border: OutlineInputBorder()),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: authority,
                      enabled: !uploading,
                      decoration: const InputDecoration(labelText: 'Authority / publisher', border: OutlineInputBorder()),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: reference,
                      enabled: !uploading,
                      decoration: const InputDecoration(labelText: 'Reference (optional)', border: OutlineInputBorder()),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: edition,
                      enabled: !uploading,
                      decoration: const InputDecoration(labelText: 'Edition / revision (optional)', border: OutlineInputBorder()),
                    ),
                    if (error != null) ...[
                      const SizedBox(height: 12),
                      Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                    ],
                  ],
                ),
              ),
            ),
            actions: [
              TextButton(
                onPressed: uploading ? null : () => Navigator.pop(dialogContext),
                child: const Text('Cancel'),
              ),
              FilledButton.icon(
                onPressed: uploading
                    ? null
                    : () async {
                        final file = selected;
                        if (file?.bytes == null || title.text.trim().isEmpty || authority.text.trim().isEmpty) {
                          setDialogState(() => error = 'Choose a PDF and enter its title and authority.');
                          return;
                        }
                        setDialogState(() {
                          uploading = true;
                          error = null;
                        });
                        try {
                          if (replacing == null) {
                            await _service.uploadPdf(
                              bytes: file!.bytes!,
                              filename: file.name,
                              title: title.text,
                              authority: authority.text,
                              reference: reference.text,
                              edition: edition.text,
                            );
                          } else {
                            await _service.replacePdf(
                              document: replacing,
                              bytes: file!.bytes!,
                              filename: file.name,
                              title: title.text,
                              authority: authority.text,
                              reference: reference.text,
                              edition: edition.text,
                            );
                          }
                          if (dialogContext.mounted) Navigator.pop(dialogContext);
                          if (mounted) {
                            setState(_refresh);
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(content: Text(replacing == null ? 'Standard added.' : 'New revision created.')),
                            );
                          }
                        } catch (e) {
                          setDialogState(() {
                            uploading = false;
                            error = e.toString();
                          });
                        }
                      },
                icon: uploading
                    ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Icon(Icons.upload_file_rounded),
                label: Text(uploading ? 'Indexing…' : replacing == null ? 'Upload' : 'Create revision'),
              ),
            ],
          ),
        ),
      );
    } finally {
      title.dispose();
      authority.dispose();
      reference.dispose();
      edition.dispose();
    }
  }

  Future<void> _archive(EngineeringStandardDocument document) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Archive standard?'),
        content: Text('${document.title} will disappear from normal search, but its PDF and citation history will be retained.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Archive')),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await _service.archive(document.id);
      if (mounted) setState(_refresh);
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
    }
  }

  Future<void> _restore(EngineeringStandardDocument document) async {
    try {
      await _service.restore(document.id);
      if (mounted) setState(_refresh);
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
    }
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          Wrap(
            alignment: WrapAlignment.spaceBetween,
            crossAxisAlignment: WrapCrossAlignment.center,
            spacing: 16,
            runSpacing: 12,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Standards Library', style: Theme.of(context).textTheme.headlineSmall),
                  const SizedBox(height: 4),
                  const Text('Private licensed documents with citation-safe revision history'),
                ],
              ),
              FilledButton.icon(
                onPressed: () => _showUploadDialog(),
                icon: const Icon(Icons.upload_file_rounded),
                label: const Text('Upload standard'),
              ),
            ],
          ),
          const SizedBox(height: 20),
          TextField(
            controller: _search,
            onSubmitted: (_) => _runSearch(),
            decoration: InputDecoration(
              labelText: 'Search your standards',
              hintText: 'e.g. minimum cover, buoyancy, pipe class, detention',
              prefixIcon: const Icon(Icons.search_rounded),
              suffixIcon: IconButton(
                tooltip: 'Search',
                onPressed: _runSearch,
                icon: const Icon(Icons.arrow_forward_rounded),
              ),
              border: const OutlineInputBorder(),
            ),
          ),
          SwitchListTile.adaptive(
            contentPadding: EdgeInsets.zero,
            title: const Text('Include archived revisions'),
            subtitle: const Text('Useful when checking historical SirisHydro citations.'),
            value: _includeArchived,
            onChanged: (value) => setState(() {
              _includeArchived = value;
              _refresh();
            }),
          ),
          const SizedBox(height: 8),
          FutureBuilder<List<EngineeringStandardSearchHit>>(
            future: _results,
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return const Center(child: Padding(padding: EdgeInsets.all(32), child: CircularProgressIndicator()));
              }
              if (snapshot.hasError) {
                return Card(child: Padding(padding: const EdgeInsets.all(18), child: Text('Unable to load standards: ${snapshot.error}')));
              }
              final hits = snapshot.data ?? const [];
              if (hits.isEmpty) {
                return const Card(child: Padding(padding: EdgeInsets.all(20), child: Text('No matching standards found.')));
              }
              return Column(
                children: hits
                    .map((hit) => _StandardHitCard(
                          hit: hit,
                          onOpenPage: hit.page == null ? null : () => _showPage(hit),
                          onReplace: hit.document.active ? () => _showUploadDialog(replacing: hit.document) : null,
                          onArchive: hit.document.active ? () => _archive(hit.document) : null,
                          onRestore: !hit.document.active && !hit.document.superseded ? () => _restore(hit.document) : null,
                        ))
                    .toList(growable: false),
              );
            },
          ),
          const SizedBox(height: 24),
          const Divider(),
          const SizedBox(height: 12),
          Text('Authoritative sources', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 6),
          Text(
            'These shortcuts are discovery links only. SirisOS does not scrape or redistribute protected standards content.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 12),
          for (final source in _authoritySources) _AuthoritySourceTile(source: source),
        ],
      ),
    );
  }
}

class _StandardHitCard extends StatelessWidget {
  const _StandardHitCard({
    required this.hit,
    this.onOpenPage,
    this.onReplace,
    this.onArchive,
    this.onRestore,
  });

  final EngineeringStandardSearchHit hit;
  final VoidCallback? onOpenPage;
  final VoidCallback? onReplace;
  final VoidCallback? onArchive;
  final VoidCallback? onRestore;

  @override
  Widget build(BuildContext context) {
    final document = hit.document;
    final reference = [
      if (document.reference?.isNotEmpty == true) document.reference!,
      if (document.edition?.isNotEmpty == true) document.edition!,
    ].join(' · ');
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Icon(Icons.menu_book_rounded),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(document.title, style: const TextStyle(fontWeight: FontWeight.w700)),
                  const SizedBox(height: 3),
                  Text(document.authority),
                  if (reference.isNotEmpty) Text(reference, style: Theme.of(context).textTheme.bodySmall),
                  if (hit.page != null) ...[
                    const SizedBox(height: 8),
                    Text('Page ${hit.page}', style: Theme.of(context).textTheme.labelMedium),
                  ],
                  if (hit.snippet?.isNotEmpty == true) ...[
                    const SizedBox(height: 4),
                    Text(hit.snippet!),
                  ],
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      Chip(label: Text('rev. ${document.revision}')),
                      Chip(label: Text('${document.pages} pages')),
                      Chip(
                        avatar: Icon(document.indexed ? Icons.check_circle_rounded : Icons.image_rounded, size: 16),
                        label: Text(document.indexedByOcr ? 'OCR searchable' : document.indexed ? 'Searchable' : 'Not indexed'),
                      ),
                      if (!document.active)
                        Chip(
                          avatar: const Icon(Icons.archive_rounded, size: 16),
                          label: Text(document.superseded ? 'Superseded' : 'Archived'),
                        ),
                      if (onOpenPage != null)
                        OutlinedButton.icon(onPressed: onOpenPage, icon: const Icon(Icons.article_rounded), label: const Text('View source page')),
                    ],
                  ),
                ],
              ),
            ),
            PopupMenuButton<String>(
              tooltip: 'Document actions',
              onSelected: (value) {
                if (value == 'replace') onReplace?.call();
                if (value == 'archive') onArchive?.call();
                if (value == 'restore') onRestore?.call();
              },
              itemBuilder: (context) => [
                if (onReplace != null) const PopupMenuItem(value: 'replace', child: Text('Replace with new revision')),
                if (onArchive != null) const PopupMenuItem(value: 'archive', child: Text('Archive')),
                if (onRestore != null) const PopupMenuItem(value: 'restore', child: Text('Restore')),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _AuthoritySource {
  const _AuthoritySource(this.name, this.description, this.url);
  final String name;
  final String description;
  final String url;
}

const _authoritySources = <_AuthoritySource>[
  _AuthoritySource('Standards Australia', 'Australian Standards catalogue and access services', 'https://www.standards.org.au/'),
  _AuthoritySource('WSAA', 'Water Services Association of Australia codes and resources', 'https://www.wsaa.asn.au/'),
  _AuthoritySource('Sydney Water', 'Technical specifications, standards and developer resources', 'https://www.sydneywater.com.au/'),
  _AuthoritySource('Austroads', 'Road and transport guidance publications', 'https://austroads.com.au/'),
  _AuthoritySource('Australian Rainfall & Runoff', 'National flood estimation guideline and supporting resources', 'https://arr.ga.gov.au/'),
];

class _AuthoritySourceTile extends StatelessWidget {
  const _AuthoritySourceTile({required this.source});
  final _AuthoritySource source;

  @override
  Widget build(BuildContext context) => ListTile(
        contentPadding: EdgeInsets.zero,
        leading: const Icon(Icons.open_in_new_rounded),
        title: Text(source.name),
        subtitle: Text(source.description),
        trailing: const Icon(Icons.chevron_right_rounded),
        onTap: () => launchUrl(Uri.parse(source.url), mode: LaunchMode.externalApplication),
      );
}
