import 'dart:async';

import 'package:flutter/material.dart';

import '../core/manual_context_override.dart';
import '../core/siris_context_service.dart';
import '../core/siris_event_bus.dart';
import 'siris_design_system.dart';

class ContextPanel extends StatefulWidget {
  const ContextPanel({super.key});

  @override
  State<ContextPanel> createState() => _ContextPanelState();
}

class _ContextPanelState extends State<ContextPanel> {
  final ManualContextOverrideService _overrideService = ManualContextOverrideService();
  StreamSubscription<SirisEvent>? _events;
  ManualContextOverride? _activeOverride;

  @override
  void initState() {
    super.initState();
    _loadOverride();
    _events = SirisEventBus.instance.on<ContextSnapshotChanged>().listen((_) {
      if (!mounted) return;
      _loadOverride();
    });
  }

  @override
  void dispose() {
    _events?.cancel();
    super.dispose();
  }

  Future<void> _loadOverride() async {
    final override = await _overrideService.current();
    if (mounted) setState(() => _activeOverride = override);
  }

  Future<void> _clearOverride() async {
    await _overrideService.clear();
    await SirisCoreContextService.instance.refresh();
    await _loadOverride();
  }

  Future<void> _openSetOverrideDialog() async {
    final result = await showDialog<_OverrideDraft>(
      context: context,
      builder: (_) => const _SetOverrideDialog(),
    );
    if (result == null) return;
    await _overrideService.set(
      label: result.label,
      domain: result.domain,
      detail: result.detail,
      expiresIn: result.expiresIn,
    );
    await SirisCoreContextService.instance.refresh();
    await _loadOverride();
  }

  @override
  Widget build(BuildContext context) {
    final service = SirisCoreContextService.instance;
    final snapshot = service.snapshot;
    final primary = snapshot.primary;
    final timeline = service.timeline.take(5).toList(growable: false);

    return SirisPanel(
      title: 'Current context',
      subtitle: primary == null
          ? 'Context providers are still initializing.'
          : 'Primary: ${primary.label}',
      icon: Icons.psychology_alt_rounded,
      trailing: _activeOverride != null
          ? IconButton(
              tooltip: 'Clear override',
              icon: const Icon(Icons.cancel_rounded),
              onPressed: _clearOverride,
            )
          : IconButton(
              tooltip: 'Set context override',
              icon: const Icon(Icons.edit_note_rounded),
              onPressed: _openSetOverrideDialog,
            ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (snapshot.facts.isEmpty)
            const Text('No active context facts yet.')
          else
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: snapshot.facts
                  .map(
                    (fact) => SirisStatusChip(
                      label: fact.label,
                      status: fact.priority >= 90
                          ? SirisStatus.critical
                          : fact.priority >= 70
                              ? SirisStatus.warning
                              : SirisStatus.success,
                    ),
                  )
                  .toList(growable: false),
            ),
          if (_activeOverride != null) ...[
            const SizedBox(height: 10),
            Text(
              _activeOverride!.expiresAt == null
                  ? 'Manual override -- no expiry, tap the icon above to clear it.'
                  : 'Manual override -- clears automatically at ${_formatTime(_activeOverride!.expiresAt!)}.',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
            ),
          ],
          if (timeline.isNotEmpty) ...[
            const SizedBox(height: 18),
            Text('Recent context changes', style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: 8),
            for (final entry in timeline)
              Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Row(
                  children: [
                    Icon(
                      entry.active ? Icons.add_circle_outline_rounded : Icons.remove_circle_outline_rounded,
                      size: 16,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        '${entry.active ? 'Entered' : 'Cleared'} ${entry.label}',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ),
                    Text(
                      _formatTime(entry.occurredAt),
                      style: Theme.of(context).textTheme.labelSmall,
                    ),
                  ],
                ),
              ),
          ],
        ],
      ),
    );
  }
}

String _formatTime(DateTime value) {
  final local = value.toLocal();
  final hour = local.hour.toString().padLeft(2, '0');
  final minute = local.minute.toString().padLeft(2, '0');
  return '$hour:$minute';
}

class _OverrideDraft {
  const _OverrideDraft({
    required this.label,
    required this.domain,
    this.detail,
    this.expiresIn,
  });

  final String label;
  final SirisContextDomain domain;
  final String? detail;
  final Duration? expiresIn;
}

const Map<String, Duration?> _expiryOptions = {
  '1 hour': Duration(hours: 1),
  '4 hours': Duration(hours: 4),
  '8 hours': Duration(hours: 8),
  'No expiry': null,
};

class _SetOverrideDialog extends StatefulWidget {
  const _SetOverrideDialog();

  @override
  State<_SetOverrideDialog> createState() => _SetOverrideDialogState();
}

class _SetOverrideDialogState extends State<_SetOverrideDialog> {
  final _labelController = TextEditingController();
  final _detailController = TextEditingController();
  SirisContextDomain _domain = SirisContextDomain.personal;
  String _expiryLabel = '4 hours';

  @override
  void dispose() {
    _labelController.dispose();
    _detailController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final label = _labelController.text.trim();
    return AlertDialog(
      title: const Text('Set context override'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            TextField(
              controller: _labelController,
              autofocus: true,
              decoration: const InputDecoration(labelText: 'Label (e.g. "Focused", "Away from home")'),
              onChanged: (_) => setState(() {}),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _detailController,
              decoration: const InputDecoration(labelText: 'Detail (optional)'),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<SirisContextDomain>(
              initialValue: _domain,
              decoration: const InputDecoration(labelText: 'Domain'),
              items: SirisContextDomain.values
                  .map((value) => DropdownMenuItem(value: value, child: Text(value.name)))
                  .toList(growable: false),
              onChanged: (value) {
                if (value != null) setState(() => _domain = value);
              },
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              initialValue: _expiryLabel,
              decoration: const InputDecoration(labelText: 'Expires'),
              items: _expiryOptions.keys
                  .map((value) => DropdownMenuItem(value: value, child: Text(value)))
                  .toList(growable: false),
              onChanged: (value) {
                if (value != null) setState(() => _expiryLabel = value);
              },
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: label.isEmpty
              ? null
              : () => Navigator.of(context).pop(
                    _OverrideDraft(
                      label: label,
                      domain: _domain,
                      detail: _detailController.text.trim().isEmpty ? null : _detailController.text.trim(),
                      expiresIn: _expiryOptions[_expiryLabel],
                    ),
                  ),
          child: const Text('Set'),
        ),
      ],
    );
  }
}
