import 'package:flutter/material.dart';

import '../models/run_record.dart';
import '../services/running_service.dart';
import '../widgets/metric_line_chart.dart';
import '../widgets/training_load_card.dart';

class RunningScreen extends StatefulWidget {
  const RunningScreen({this.addRequest = 0, super.key});

  final int addRequest;

  @override
  State<RunningScreen> createState() => _RunningScreenState();
}

class _RunningScreenState extends State<RunningScreen> {
  final _service = RunningService();
  late Future<List<RunRecord>> _runsFuture;

  @override
  void initState() {
    super.initState();
    _runsFuture = _service.fetchRuns();
  }

  @override
  void didUpdateWidget(covariant RunningScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.addRequest != oldWidget.addRequest) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _addRun();
      });
    }
  }

  void _reload() => setState(() {
        _runsFuture = _service.fetchRuns();
      });

  Future<void> _addRun() async {
    final saved = await showDialog<bool>(
      context: context,
      builder: (_) => const _RunEntryDialog(),
    );
    if (saved == true) _reload();
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: FutureBuilder<List<RunRecord>>(
        future: _runsFuture,
        builder: (context, snapshot) {
          final runs = snapshot.data ?? const <RunRecord>[];
          return RefreshIndicator(
            onRefresh: () async => _reload(),
            child: ListView(
              padding: const EdgeInsets.all(20),
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Running', style: Theme.of(context).textTheme.headlineMedium),
                          const SizedBox(height: 6),
                          Text(
                            'Track runs and your rolling fitness trend.',
                            style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant),
                          ),
                        ],
                      ),
                    ),
                    FilledButton.icon(
                      onPressed: _addRun,
                      icon: const Icon(Icons.add_rounded),
                      label: const Text('Add run'),
                    ),
                  ],
                ),
                const SizedBox(height: 20),
                const TrainingLoadCard(),
                const SizedBox(height: 20),
                if (snapshot.connectionState == ConnectionState.waiting)
                  const Center(child: Padding(padding: EdgeInsets.all(40), child: CircularProgressIndicator()))
                else if (snapshot.hasError)
                  const Card(child: Padding(padding: EdgeInsets.all(20), child: Text('Could not load running data.')))
                else if (runs.isEmpty)
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: Column(
                        children: [
                          const Icon(Icons.directions_run_rounded, size: 52),
                          const SizedBox(height: 12),
                          Text('No runs recorded yet', style: Theme.of(context).textTheme.titleLarge),
                          const SizedBox(height: 6),
                          const Text('Add your first run to start building the fitness graph.'),
                        ],
                      ),
                    ),
                  )
                else ...[
                  MetricLineChart(
                    title: 'Running fitness score',
                    samples: runs.reversed
                        .map((run) => MetricSample(time: run.runDate, value: run.fitnessScore))
                        .toList(growable: false),
                    valueSuffix: '',
                    maxY: 100,
                  ),
                  const SizedBox(height: 16),
                  Text('Run history', style: Theme.of(context).textTheme.titleLarge),
                  const SizedBox(height: 10),
                  ...runs.map((run) => Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: Card(
                          child: ListTile(
                            leading: CircleAvatar(child: Icon(run.runType == 'outdoor' ? Icons.terrain_rounded : Icons.fitness_center_rounded)),
                            title: Text('${run.distanceKm.toStringAsFixed(2)} km · ${run.paceLabel}'),
                            subtitle: Text('${_dateLabel(run.runDate)} · ${run.runType} · ${run.averageHeartRate} bpm'),
                            trailing: Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              crossAxisAlignment: CrossAxisAlignment.end,
                              children: [
                                Text(run.effortScore.toStringAsFixed(1), style: Theme.of(context).textTheme.titleMedium),
                                const Text('effort'),
                              ],
                            ),
                          ),
                        ),
                      )),
                  const SizedBox(height: 8),
                  Text(
                    'The score is a personal comparison metric based on pace, distance and average heart rate. It is not a medical assessment.',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant),
                  ),
                ],
              ],
            ),
          );
        },
      ),
    );
  }

  String _dateLabel(DateTime date) => '${date.day}/${date.month}/${date.year}';
}

class _RunEntryDialog extends StatefulWidget {
  const _RunEntryDialog();

  @override
  State<_RunEntryDialog> createState() => _RunEntryDialogState();
}

class _RunEntryDialogState extends State<_RunEntryDialog> {
  final _formKey = GlobalKey<FormState>();
  final _distance = TextEditingController();
  final _pace = TextEditingController();
  final _heartRate = TextEditingController();
  final _service = RunningService();
  DateTime _date = DateTime.now();
  String _type = 'outdoor';
  bool _saving = false;

  @override
  void dispose() {
    _distance.dispose();
    _pace.dispose();
    _heartRate.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    final paceParts = _pace.text.trim().split(':');
    final paceSeconds = int.parse(paceParts[0]) * 60 + int.parse(paceParts[1]);
    setState(() => _saving = true);
    try {
      await _service.createRun(
        date: _date,
        type: _type,
        distanceKm: double.parse(_distance.text),
        paceSecondsPerKm: paceSeconds,
        averageHeartRate: int.parse(_heartRate.text),
      );
      if (mounted) Navigator.pop(context, true);
    } catch (_) {
      if (mounted) {
        setState(() => _saving = false);
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Could not save run.')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Add run'),
      content: SizedBox(
        width: 420,
        child: Form(
          key: _formKey,
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Date'),
                  subtitle: Text('${_date.day}/${_date.month}/${_date.year}'),
                  trailing: const Icon(Icons.calendar_month_rounded),
                  onTap: () async {
                    final value = await showDatePicker(context: context, firstDate: DateTime(2020), lastDate: DateTime.now(), initialDate: _date);
                    if (value != null) setState(() => _date = value);
                  },
                ),
                DropdownButtonFormField<String>(
                  value: _type,
                  decoration: const InputDecoration(labelText: 'Type'),
                  items: const [
                    DropdownMenuItem(value: 'outdoor', child: Text('Outdoor')),
                    DropdownMenuItem(value: 'treadmill', child: Text('Treadmill')),
                  ],
                  onChanged: (value) => setState(() => _type = value ?? 'outdoor'),
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _distance,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  decoration: const InputDecoration(labelText: 'Distance', suffixText: 'km'),
                  validator: (value) => (double.tryParse(value ?? '') ?? 0) <= 0 ? 'Enter a valid distance' : null,
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _pace,
                  keyboardType: TextInputType.datetime,
                  decoration: const InputDecoration(labelText: 'Average pace', hintText: '5:30', suffixText: '/km'),
                  validator: (value) {
                    final parts = (value ?? '').split(':');
                    if (parts.length != 2) return 'Use m:ss format';
                    final minutes = int.tryParse(parts[0]);
                    final seconds = int.tryParse(parts[1]);
                    return minutes == null || seconds == null || seconds > 59 ? 'Use m:ss format' : null;
                  },
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _heartRate,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(labelText: 'Average heart rate', suffixText: 'bpm'),
                  validator: (value) {
                    final hr = int.tryParse(value ?? '');
                    return hr == null || hr < 40 || hr > 240 ? 'Enter a valid heart rate' : null;
                  },
                ),
              ],
            ),
          ),
        ),
      ),
      actions: [
        TextButton(onPressed: _saving ? null : () => Navigator.pop(context), child: const Text('Cancel')),
        FilledButton(onPressed: _saving ? null : _save, child: Text(_saving ? 'Saving…' : 'Save run')),
      ],
    );
  }
}
