import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';

import '../services/engineering_standards_service.dart';

class EngineeringStandardsScreen extends StatefulWidget {
  const EngineeringStandardsScreen({super.key});

  @override
  State<EngineeringStandardsScreen> createState() =>
      _EngineeringStandardsScreenState();
}

class _EngineeringStandardsScreenState extends State<EngineeringStandardsScreen> {
  final _service = EngineeringStandardsService();
  final _search = TextEditingController();
  late Future<List<EngineeringStandardSearchHit>> _results;

  @override
  void initState() {
    super.initState();
    _results = _service.search();
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  void _runSearch() {
    setState(() => _results = _service.search(query: _search.text.trim()));
  }

  Future<void> _showPage(EngineeringStandardSearchHit hit) async {
    final pageNumber = hit.page;
    if (pageNumber == null) return;
    await showDialog<void>(
      context: context,
      builder: (context) => Dialog(
        child: SizedBox(
          width: 760,
          height: 640,
          child: FutureBuilder<EngineeringStandardPage>(
            future: _service.page(documentId: hit.document.id, page: pageNumber),
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return const Center(child: CircularProgressIndicator());
              }
              if (snapshot.hasError) {
                return Padding(
                  padding: const EdgeInsets.all(24),
                  child: Text('Unable to load page: ${snapshot.error}'),
                );
              }
              final page = snapshot.requireData;
              return Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(page.document.title, style: Theme.of(context).textTheme.titleLarge),
                              const SizedBox(height: 4),
                              Text(page.citation, style: Theme.of(context).textTheme.labelLarge),
                            ],
                          ),
                        ),
                        IconButton(
                          tooltip: 'Close',
                          onPressed: () => Navigator.pop(context),
                          icon: const Icon(Icons.close_rounded),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Wrap(
                      spacing: 8,
                      children: [
                        OutlinedButton.icon(
                          onPressed: () async {
                            await Clipboard.setData(ClipboardData(text: page.citation));
                            if (context.mounted) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(content: Text('Citation copied.')),
                              );
                            }
                          },
                          icon: const Icon(Icons.copy_rounded),
                          label: const Text('Copy citation'),
                        ),
                        Chip(label: Text('Page ${page.page}')),
                      ],
                    ),
                    const SizedBox(height: 12),
                    const Divider(),
                    const SizedBox(height: 8),
                    Expanded(
                      child: SelectionArea(
                        child: SingleChildScrollView(
                          child: Text(
                            page.text.trim().isEmpty
                                ? 'No extractable text is available for this page.'
                                : page.text,
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Extracted local text for retrieval and verification. Check the licensed PDF when layout, figures or tables are material.',
                      style: Theme.of(context).textTheme.bodySmall,
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

  Future<void> _showUploadDialog() async {
    final title = TextEditingController();
    final authority = TextEditingController();
    final reference = TextEditingController();
    final edition = TextEditingController();
    PlatformFile? selected;
    bool uploading = false;
    String? error;

    try {
      await showDialog<void>(
        context: context,
        barrierDismissible: !uploading,
        builder: (dialogContext) => StatefulBuilder(
          builder: (context, setDialogState) => AlertDialog(
            title: const Text('Add licensed standard'),
            content: SizedBox(
              width: 560,
              child: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Upload a PDF you are entitled to store and use. SirisOS keeps it private on this server and indexes extracted text for local search.',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                    const SizedBox(height: 16),
                    OutlinedButton.icon(
                      onPressed: uploading
                          ? null
                          : () async {
                              final result = await FilePicker.pickFiles(
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
                      decoration: const InputDecoration(
                        labelText: 'Authority / publisher',
                        hintText: 'e.g. Standards Australia, Sydney Water, WSAA',
                        border: OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: reference,
                      enabled: !uploading,
                      decoration: const InputDecoration(
                        labelText: 'Reference (optional)',
                        hintText: 'e.g. AS 3725',
                        border: OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: edition,
                      enabled: !uploading,
                      decoration: const InputDecoration(
                        labelText: 'Edition / revision (optional)',
                        border: OutlineInputBorder(),
                      ),
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
                          await _service.uploadPdf(
                            bytes: file!.bytes!,
                            filename: file.name,
                            title: title.text,
                            authority: authority.text,
                            reference: reference.text,
                            edition: edition.text,
                          );
                          if (dialogContext.mounted) Navigator.pop(dialogContext);
                          if (mounted) {
                            setState(() => _results = _service.search());
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(content: Text('Standard added to private library.')),
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
                label: Text(uploading ? 'Indexing…' : 'Upload'),
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
                  const Text('Private licensed documents + authoritative source catalogue'),
                ],
              ),
              FilledButton.icon(
                onPressed: _showUploadDialog,
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
          const SizedBox(height: 20),
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
                return const Card(
                  child: Padding(
                    padding: EdgeInsets.all(20),
                    child: Text('No matching private standards yet. Upload a licensed PDF to begin.'),
                  ),
                );
              }
              return Column(
                children: hits
                    .map((hit) => _StandardHitCard(hit: hit, onOpenPage: hit.page == null ? null : () => _showPage(hit)))
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
  const _StandardHitCard({required this.hit, this.onOpenPage});
  final EngineeringStandardSearchHit hit;
  final VoidCallback? onOpenPage;

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
                  if (reference.isNotEmpty) ...[
                    const SizedBox(height: 2),
                    Text(reference, style: Theme.of(context).textTheme.bodySmall),
                  ],
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
                      Chip(label: Text('${document.pages} pages')),
                      Chip(
                        avatar: Icon(document.indexed ? Icons.check_circle_rounded : Icons.image_rounded, size: 16),
                        label: Text(document.indexed ? 'Searchable' : 'Stored · not indexed'),
                      ),
                      if (onOpenPage != null)
                        OutlinedButton.icon(
                          onPressed: onOpenPage,
                          icon: const Icon(Icons.article_rounded),
                          label: const Text('View source page'),
                        ),
                    ],
                  ),
                ],
              ),
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
