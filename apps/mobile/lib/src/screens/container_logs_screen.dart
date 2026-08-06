import 'package:flutter/material.dart';

import '../services/homelab_service.dart';

class ContainerLogsScreen extends StatefulWidget {
  const ContainerLogsScreen({
    required this.containerId,
    required this.containerName,
    super.key,
  });

  final String containerId;
  final String containerName;

  @override
  State<ContainerLogsScreen> createState() => _ContainerLogsScreenState();
}

class _ContainerLogsScreenState extends State<ContainerLogsScreen> {
  final HomelabService _service = HomelabService();
  final ScrollController _verticalController = ScrollController();
  final ScrollController _horizontalController = ScrollController();

  int _tail = 300;
  String? _logs;
  String? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _verticalController.dispose();
    _horizontalController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final logs = await _service.fetchContainerLogs(
        widget.containerId,
        tail: _tail,
      );
      if (!mounted) return;
      setState(() => _logs = logs);
    } catch (error) {
      if (!mounted) return;
      setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: Text('${widget.containerName} logs'),
        actions: [
          PopupMenuButton<int>(
            tooltip: 'Log line count',
            initialValue: _tail,
            onSelected: (value) {
              _tail = value;
              _load();
            },
            itemBuilder: (_) => const [
              PopupMenuItem(value: 100, child: Text('Last 100 lines')),
              PopupMenuItem(value: 300, child: Text('Last 300 lines')),
              PopupMenuItem(value: 500, child: Text('Last 500 lines')),
              PopupMenuItem(value: 1000, child: Text('Last 1,000 lines')),
            ],
            icon: const Icon(Icons.tune_rounded),
          ),
          IconButton(
            onPressed: _loading ? null : _load,
            tooltip: 'Refresh logs',
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Card(
          clipBehavior: Clip.antiAlias,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
                child: Row(
                  children: [
                    Icon(Icons.terminal_rounded, color: scheme.primary),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        'Last $_tail lines',
                        style: Theme.of(context).textTheme.titleSmall,
                      ),
                    ),
                    if (_loading)
                      const SizedBox.square(
                        dimension: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                  ],
                ),
              ),
              const Divider(height: 1),
              Expanded(child: _buildContent(context)),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildContent(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.error_outline_rounded, color: scheme.error, size: 42),
              const SizedBox(height: 12),
              Text(_error!, textAlign: TextAlign.center),
              const SizedBox(height: 16),
              FilledButton.icon(
                onPressed: _load,
                icon: const Icon(Icons.refresh_rounded),
                label: const Text('Try again'),
              ),
            ],
          ),
        ),
      );
    }

    final logs = _logs;
    if (_loading && logs == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (logs == null || logs.trim().isEmpty) {
      return const Center(child: Text('No log output is available.'));
    }

    return Container(
      color: scheme.surfaceContainerLowest,
      padding: const EdgeInsets.all(14),
      child: Scrollbar(
        controller: _verticalController,
        thumbVisibility: true,
        child: SingleChildScrollView(
          controller: _verticalController,
          child: SingleChildScrollView(
            controller: _horizontalController,
            scrollDirection: Axis.horizontal,
            child: SelectableText(
              logs,
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 12,
                height: 1.45,
                color: scheme.onSurface,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
