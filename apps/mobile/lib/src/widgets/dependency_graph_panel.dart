import 'package:flutter/material.dart';

import '../core/dependency_graph.dart';
import 'siris_design_system.dart';

class DependencyGraphPanel extends StatefulWidget {
  const DependencyGraphPanel({super.key, this.onChanged});

  final VoidCallback? onChanged;

  @override
  State<DependencyGraphPanel> createState() => _DependencyGraphPanelState();
}

class _DependencyGraphPanelState extends State<DependencyGraphPanel> {
  final DependencyGraph _graph = DependencyGraph.instance;
  late Future<void> _loadFuture;

  @override
  void initState() {
    super.initState();
    _loadFuture = _graph.load();
  }

  @override
  Widget build(BuildContext context) => SirisPanel(
        title: 'Digital Twin topology',
        subtitle: 'Explicit dependency relationships used for downstream impact analysis',
        icon: Icons.account_tree_rounded,
        child: FutureBuilder<void>(
          future: _loadFuture,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const LinearProgressIndicator();
            }
            final custom = _graph.customEdges;
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Wrap(
                  spacing: 12,
                  runSpacing: 10,
                  children: [
                    FilledButton.icon(
                      onPressed: _addDependency,
                      icon: const Icon(Icons.add_link_rounded),
                      label: const Text('Add dependency'),
                    ),
                    if (custom.isNotEmpty)
                      TextButton.icon(
                        onPressed: _reset,
                        icon: const Icon(Icons.restart_alt_rounded),
                        label: const Text('Reset custom topology'),
                      ),
                  ],
                ),
                const SizedBox(height: 14),
                Text(
                  'Built-in',
                  style: Theme.of(context).textTheme.labelLarge,
                ),
                const SizedBox(height: 8),
                for (final edge in _graph.builtInEdges) _EdgeRow(edge: edge),
                const SizedBox(height: 12),
                Text(
                  'Custom',
                  style: Theme.of(context).textTheme.labelLarge,
                ),
                const SizedBox(height: 8),
                if (custom.isEmpty)
                  Text(
                    'No custom relationships yet. Add only topology you know is real; SirisOS will not infer physical power or network dependencies.',
                    style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant),
                  )
                else
                  for (final edge in custom)
                    _EdgeRow(
                      edge: edge,
                      onDelete: () => _remove(edge),
                    ),
              ],
            );
          },
        ),
      );

  Future<void> _addDependency() async {
    String? dependentId;
    String? dependencyId;
    final reasonController = TextEditingController();
    final result = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('Add dependency'),
          content: SizedBox(
            width: 440,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                DropdownButtonFormField<String>(
                  decoration: const InputDecoration(labelText: 'Component'),
                  initialValue: dependentId,
                  items: _graph.nodes
                      .map((node) => DropdownMenuItem(value: node.id, child: Text(node.label)))
                      .toList(growable: false),
                  onChanged: (value) => setDialogState(() => dependentId = value),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  decoration: const InputDecoration(labelText: 'Depends on'),
                  initialValue: dependencyId,
                  items: _graph.nodes
                      .map((node) => DropdownMenuItem(value: node.id, child: Text(node.label)))
                      .toList(growable: false),
                  onChanged: (value) => setDialogState(() => dependencyId = value),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: reasonController,
                  decoration: const InputDecoration(
                    labelText: 'Reason (optional)',
                    hintText: 'e.g. Docker host is powered by this UPS',
                  ),
                  maxLines: 2,
                ),
              ],
            ),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: const Text('Cancel')),
            FilledButton(
              onPressed: dependentId == null || dependencyId == null
                  ? null
                  : () => Navigator.pop(dialogContext, true),
              child: const Text('Add'),
            ),
          ],
        ),
      ),
    );

    if (result != true || dependentId == null || dependencyId == null || !mounted) {
      reasonController.dispose();
      return;
    }
    try {
      await _graph.addCustomEdge(
        dependentId: dependentId!,
        dependencyId: dependencyId!,
        reason: reasonController.text,
      );
      if (mounted) {
        setState(() {});
        widget.onChanged?.call();
      }
    } on DependencyGraphException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(error.message)));
      }
    } finally {
      reasonController.dispose();
    }
  }

  Future<void> _remove(DependencyEdge edge) async {
    try {
      await _graph.removeCustomEdge(edge.key);
      if (mounted) {
        setState(() {});
        widget.onChanged?.call();
      }
    } on DependencyGraphException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(error.message)));
      }
    }
  }

  Future<void> _reset() async {
    try {
      await _graph.resetCustomEdges();
      if (mounted) {
        setState(() {});
        widget.onChanged?.call();
      }
    } on DependencyGraphException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(error.message)));
      }
    }
  }
}

class _EdgeRow extends StatelessWidget {
  const _EdgeRow({required this.edge, this.onDelete});

  final DependencyEdge edge;
  final VoidCallback? onDelete;

  @override
  Widget build(BuildContext context) {
    final graph = DependencyGraph.instance;
    final dependent = graph.node(edge.dependentId)?.label ?? edge.dependentId;
    final dependency = graph.node(edge.dependencyId)?.label ?? edge.dependencyId;
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.subdirectory_arrow_right_rounded, size: 18),
          const SizedBox(width: 9),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('$dependent depends on $dependency', style: const TextStyle(fontWeight: FontWeight.w700)),
                const SizedBox(height: 2),
                Text(
                  edge.reason,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                ),
              ],
            ),
          ),
          if (edge.isBuiltIn)
            const SirisStatusChip(label: 'BUILT-IN', status: SirisStatus.neutral)
          else
            IconButton(
              tooltip: 'Remove custom dependency',
              onPressed: onDelete,
              icon: const Icon(Icons.delete_outline_rounded),
            ),
        ],
      ),
    );
  }
}
