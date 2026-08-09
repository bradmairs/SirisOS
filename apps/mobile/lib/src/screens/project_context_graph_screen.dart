import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../services/engineering_standards_service.dart';
import '../services/project_engineering_standard_relationships.dart';
import '../services/project_service.dart';

class ProjectContextGraphScreen extends StatefulWidget {
  const ProjectContextGraphScreen({super.key});

  @override
  State<ProjectContextGraphScreen> createState() => _ProjectContextGraphScreenState();
}

class _ProjectContextGraphScreenState extends State<ProjectContextGraphScreen> {
  final _service = ProjectService();
  final _standardsService = EngineeringStandardsService();
  late Future<_ProjectGraphData> _data;
  bool _attaching = false;

  @override
  void initState() {
    super.initState();
    _data = _load();
  }

  Future<_ProjectGraphData> _load() async {
    final current = await _service.currentProject();
    final project = current.project;
    if (project == null) return _ProjectGraphData(current: current);
    final graph = await _service.graph(project.id);
    return _ProjectGraphData(current: current, graph: graph);
  }

  void _refresh() => setState(() => _data = _load());

  Future<void> _attachStandard(ProjectRecord project) async {
    if (_attaching) return;
    final document = await showDialog<EngineeringStandardDocument>(
      context: context,
      builder: (_) => _StandardPickerDialog(service: _standardsService),
    );
    if (document == null || !mounted) return;

    setState(() => _attaching = true);
    try {
      await _service.attachEngineeringStandard(project.id, document.id);
      if (!mounted) return;
      setState(() {
        _attaching = false;
        _data = _load();
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('${_standardIdentity(document)} attached as an exact revision reference.')),
      );
    } catch (error) {
      if (!mounted) return;
      setState(() => _attaching = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Unable to attach standard: $error')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: FutureBuilder<_ProjectGraphData>(
        future: _data,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return _MessageState(
              icon: Icons.hub_outlined,
              title: 'Context graph unavailable',
              message: '${snapshot.error}',
              actionLabel: 'Try again',
              onAction: _refresh,
            );
          }

          final data = snapshot.requireData;
          final project = data.current.project;
          final graph = data.graph;
          if (project == null || graph == null) {
            return const _MessageState(
              icon: Icons.account_tree_outlined,
              title: 'No current project',
              message: 'Choose a current project first. Its explicit relationships will appear here.',
            );
          }

          return ListView(
            padding: const EdgeInsets.fromLTRB(20, 18, 20, 32),
            children: [
              Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Project context graph', style: Theme.of(context).textTheme.headlineMedium),
                        const SizedBox(height: 4),
                        Text(
                          project.name,
                          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                                color: Theme.of(context).colorScheme.primary,
                              ),
                        ),
                      ],
                    ),
                  ),
                  IconButton.filledTonal(
                    tooltip: 'Refresh graph',
                    onPressed: _refresh,
                    icon: const Icon(Icons.refresh_rounded),
                  ),
                ],
              ),
              const SizedBox(height: 6),
              Text(
                'Only explicit, provenance-backed relationships are shown. SirisOS does not infer project membership.',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
              ),
              const SizedBox(height: 12),
              Align(
                alignment: Alignment.centerLeft,
                child: FilledButton.tonalIcon(
                  onPressed: _attaching ? null : () => _attachStandard(project),
                  icon: _attaching
                      ? const SizedBox.square(
                          dimension: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.library_books_rounded),
                  label: Text(_attaching ? 'Attaching…' : 'Attach Engineering standard'),
                ),
              ),
              const SizedBox(height: 18),
              Card(
                child: SizedBox(
                  height: 420,
                  child: graph.nodes.length <= 1
                      ? const Center(
                          child: Padding(
                            padding: EdgeInsets.all(24),
                            child: Text(
                              'This project has no attached context yet. Attach Knowledge notes from Projects or add an Engineering standard here to grow the graph.',
                              textAlign: TextAlign.center,
                            ),
                          ),
                        )
                      : Padding(
                          padding: const EdgeInsets.all(18),
                          child: CustomPaint(
                            painter: _ProjectGraphPainter(
                              graph: graph,
                              theme: Theme.of(context),
                            ),
                            child: const SizedBox.expand(),
                          ),
                        ),
                ),
              ),
              const SizedBox(height: 14),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: const [
                  _LegendChip(icon: Icons.folder_rounded, label: 'Project'),
                  _LegendChip(icon: Icons.menu_book_rounded, label: 'Knowledge note'),
                  _LegendChip(icon: Icons.library_books_rounded, label: 'Engineering standard'),
                  _LegendChip(icon: Icons.inventory_2_outlined, label: 'Part of project'),
                  _LegendChip(icon: Icons.link_rounded, label: 'Reference'),
                ],
              ),
              const SizedBox(height: 22),
              Text('Relationships · ${graph.edges.length}', style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 10),
              if (graph.edges.isEmpty)
                Text(
                  'No explicit relationships yet.',
                  style: Theme.of(context).textTheme.bodyMedium,
                )
              else
                for (final edge in graph.edges)
                  Card(
                    child: ListTile(
                      leading: Icon(_targetIcon(graph, edge.target, edge.kind)),
                      title: Text(_targetLabel(graph, edge.target)),
                      subtitle: Text('${edge.label} · ${edge.provenance}'),
                    ),
                  ),
            ],
          );
        },
      ),
    );
  }

  ProjectGraphNode? _targetNode(ProjectGraph graph, String targetId) {
    for (final node in graph.nodes) {
      if (node.id == targetId) return node;
    }
    return null;
  }

  String _targetLabel(ProjectGraph graph, String targetId) =>
      _targetNode(graph, targetId)?.label ?? targetId;

  IconData _targetIcon(ProjectGraph graph, String targetId, String kind) {
    final node = _targetNode(graph, targetId);
    if (node?.nodeType == 'engineering_standard') return Icons.library_books_rounded;
    if (node?.nodeType == 'knowledge_note') return Icons.menu_book_rounded;
    return kind == 'contains' ? Icons.inventory_2_outlined : Icons.link_rounded;
  }
}

class _StandardPickerDialog extends StatefulWidget {
  const _StandardPickerDialog({required this.service});
  final EngineeringStandardsService service;

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

  void _runSearch() => setState(
        () => _results = widget.service.search(query: _search.text.trim()),
      );

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
      title: const Text('Attach Engineering standard'),
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
                        title: Text(_standardIdentity(document)),
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

String _standardIdentity(EngineeringStandardDocument document) {
  final parts = <String>[
    if (document.reference?.trim().isNotEmpty == true) document.reference!.trim() else document.title,
    if (document.edition?.trim().isNotEmpty == true) document.edition!.trim(),
    if (document.revision > 1) 'library rev. ${document.revision}',
  ];
  return parts.join(' · ');
}

class _ProjectGraphData {
  const _ProjectGraphData({required this.current, this.graph});
  final CurrentProjectState current;
  final ProjectGraph? graph;
}

class _MessageState extends StatelessWidget {
  const _MessageState({
    required this.icon,
    required this.title,
    required this.message,
    this.actionLabel,
    this.onAction,
  });

  final IconData icon;
  final String title;
  final String message;
  final String? actionLabel;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 52),
            const SizedBox(height: 14),
            Text(title, style: Theme.of(context).textTheme.titleLarge, textAlign: TextAlign.center),
            const SizedBox(height: 8),
            Text(message, textAlign: TextAlign.center),
            if (actionLabel != null && onAction != null) ...[
              const SizedBox(height: 16),
              FilledButton.tonal(onPressed: onAction, child: Text(actionLabel!)),
            ],
          ],
        ),
      ),
    );
  }
}

class _LegendChip extends StatelessWidget {
  const _LegendChip({required this.icon, required this.label});
  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) => Chip(
        avatar: Icon(icon, size: 16),
        label: Text(label),
        visualDensity: VisualDensity.compact,
      );
}

class _ProjectGraphPainter extends CustomPainter {
  _ProjectGraphPainter({required this.graph, required this.theme});

  final ProjectGraph graph;
  final ThemeData theme;

  @override
  void paint(Canvas canvas, Size size) {
    final centerNode = graph.nodes.firstWhere(
      (node) => node.center,
      orElse: () => graph.nodes.first,
    );
    final neighbors = graph.nodes.where((node) => node.id != centerNode.id).toList(growable: false);
    final center = Offset(size.width / 2, size.height / 2);
    final radius = math.min(size.width, size.height) * 0.34;
    final positions = <String, Offset>{centerNode.id: center};

    for (var i = 0; i < neighbors.length; i++) {
      final angle = (math.pi * 2 * i / neighbors.length) - math.pi / 2;
      positions[neighbors[i].id] = Offset(
        center.dx + radius * math.cos(angle),
        center.dy + radius * math.sin(angle),
      );
    }

    for (final edge in graph.edges) {
      final start = positions[edge.source];
      final end = positions[edge.target];
      if (start == null || end == null) continue;
      final paint = Paint()
        ..color = theme.colorScheme.outlineVariant
        ..strokeWidth = edge.kind == 'contains' ? 2.2 : 1.4;
      canvas.drawLine(start, end, paint);
    }

    for (final node in graph.nodes) {
      final point = positions[node.id];
      if (point == null) continue;
      final isCenter = node.id == centerNode.id;
      final paint = Paint()
        ..color = isCenter
            ? theme.colorScheme.primaryContainer
            : theme.colorScheme.surfaceContainerHighest;
      canvas.drawCircle(point, isCenter ? 38 : 30, paint);

      final textPainter = TextPainter(
        text: TextSpan(
          text: _short(node.label),
          style: theme.textTheme.labelSmall?.copyWith(
            color: isCenter
                ? theme.colorScheme.onPrimaryContainer
                : theme.colorScheme.onSurfaceVariant,
            fontWeight: isCenter ? FontWeight.w700 : FontWeight.w500,
          ),
        ),
        textAlign: TextAlign.center,
        maxLines: 2,
        textDirection: TextDirection.ltr,
        ellipsis: '…',
      )..layout(maxWidth: isCenter ? 105 : 88);
      textPainter.paint(
        canvas,
        point - Offset(textPainter.width / 2, textPainter.height / 2),
      );
    }
  }

  String _short(String value) => value.length <= 30 ? value : '${value.substring(0, 27)}…';

  @override
  bool shouldRepaint(covariant _ProjectGraphPainter oldDelegate) =>
      oldDelegate.graph != graph || oldDelegate.theme != theme;
}
