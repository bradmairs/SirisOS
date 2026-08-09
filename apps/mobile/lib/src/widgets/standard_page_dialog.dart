import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../services/engineering_standards_service.dart';

/// Shows the exact cited page of a private standards-library document.
/// Shared between the Standards library and any other module (e.g.
/// SirisHydro) that needs to jump from a citation to its source page.
Future<void> showStandardPageDialog(
  BuildContext context, {
  required EngineeringStandardsService service,
  required String documentId,
  required int page,
}) {
  return showDialog<void>(
    context: context,
    builder: (context) => Dialog(
      child: SizedBox(
        width: 760,
        height: 640,
        child: FutureBuilder<EngineeringStandardPage>(
          future: service.page(documentId: documentId, page: page),
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
            final loadedPage = snapshot.requireData;
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
                            Text(loadedPage.document.title, style: Theme.of(context).textTheme.titleLarge),
                            const SizedBox(height: 4),
                            Text(loadedPage.citation, style: Theme.of(context).textTheme.labelLarge),
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
                          await Clipboard.setData(ClipboardData(text: loadedPage.citation));
                          if (context.mounted) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(content: Text('Citation copied.')),
                            );
                          }
                        },
                        icon: const Icon(Icons.copy_rounded),
                        label: const Text('Copy citation'),
                      ),
                      Chip(label: Text('Page ${loadedPage.page}')),
                      Chip(label: Text('Library rev. ${loadedPage.document.revision}')),
                    ],
                  ),
                  const SizedBox(height: 12),
                  const Divider(),
                  const SizedBox(height: 8),
                  Expanded(
                    child: SelectionArea(
                      child: SingleChildScrollView(
                        child: Text(
                          loadedPage.text.trim().isEmpty
                              ? 'No extractable text is available for this page.'
                              : loadedPage.text,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Historical revisions remain directly retrievable so old citations keep pointing to the exact source they originally referenced.',
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
