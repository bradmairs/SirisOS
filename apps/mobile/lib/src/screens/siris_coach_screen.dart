import 'dart:async';

import 'package:flutter/material.dart';

import '../core/siris_event_bus.dart';
import '../models/achievement.dart';
import '../models/ask_siris_answer.dart';
import '../models/coach_report.dart';
import '../models/training_conflict_check.dart';
import '../services/coach_service.dart';
import '../theme/app_theme.dart';

class SirisCoachScreen extends StatefulWidget {
  const SirisCoachScreen({super.key});

  @override
  State<SirisCoachScreen> createState() => _SirisCoachScreenState();
}

class _SirisCoachScreenState extends State<SirisCoachScreen> {
  final CoachService _service = CoachService();
  late Future<WeeklyCoachReport> _future;
  late Future<TrainingConflictCheck> _conflictFuture;
  late Future<List<Achievement>> _achievementsFuture;
  StreamSubscription<SirisEvent>? _eventSubscription;

  @override
  void initState() {
    super.initState();
    _future = _service.fetchWeeklyReport();
    _conflictFuture = _service.fetchConflictCheck();
    _achievementsFuture = _service.fetchAchievements();
    _eventSubscription =
        SirisEventBus.instance.on<ModuleDataChanged>().listen((event) {
      if (event.moduleId == 'health') _refresh();
    });
  }

  @override
  void dispose() {
    _eventSubscription?.cancel();
    super.dispose();
  }

  Future<void> _refresh() async {
    final next = _service.fetchWeeklyReport();
    final nextConflict = _service.fetchConflictCheck();
    final nextAchievements = _service.fetchAchievements();
    setState(() {
      _future = next;
      _conflictFuture = nextConflict;
      _achievementsFuture = nextAchievements;
    });
    await next;
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: FutureBuilder<WeeklyCoachReport>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return _CoachError(
                message: snapshot.error.toString(), onRetry: _refresh);
          }

          final report = snapshot.data!;
          return RefreshIndicator(
            onRefresh: _refresh,
            child: LayoutBuilder(
              builder: (context, constraints) {
                final columns = constraints.maxWidth >= 1100
                    ? 4
                    : constraints.maxWidth >= 650
                        ? 2
                        : 1;
                final horizontalPadding = constraints.maxWidth >= 900 ? 28.0 : 20.0;
                final availableWidth = constraints.maxWidth - horizontalPadding * 2;
                final tileWidth = (availableWidth - (columns - 1) * 16) / columns;

                return ListView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: EdgeInsets.fromLTRB(horizontalPadding, 24, horizontalPadding, 32),
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text('Coach', style: Theme.of(context).textTheme.headlineMedium),
                              const SizedBox(height: 6),
                              Text(
                                'This week, in plain terms.',
                                style: TextStyle(
                                    color: Theme.of(context).colorScheme.onSurfaceVariant),
                              ),
                            ],
                          ),
                        ),
                        IconButton.filledTonal(
                          onPressed: _refresh,
                          tooltip: 'Refresh',
                          icon: const Icon(Icons.refresh_rounded),
                        ),
                      ],
                    ),
                    const SizedBox(height: 20),
                    _TodayCard(future: _conflictFuture),
                    const SizedBox(height: 20),
                    _HeadlineCard(report: report),
                    const SizedBox(height: 20),
                    Wrap(
                      spacing: 16,
                      runSpacing: 16,
                      children: [
                        SizedBox(
                          width: tileWidth,
                          child: _MetricTile(
                            icon: Icons.directions_run_rounded,
                            color: const Color(0xFF38BDF8),
                            label: 'Running',
                            value: '${report.runningDistanceKm.toStringAsFixed(1)} km',
                            delta: report.runningDistanceKmDelta,
                            deltaUnit: 'km',
                          ),
                        ),
                        SizedBox(
                          width: tileWidth,
                          child: _MetricTile(
                            icon: Icons.event_repeat_rounded,
                            color: const Color(0xFF63D83A),
                            label: 'Runs logged',
                            value: '${report.runCount}',
                            delta: report.runCountDelta?.toDouble(),
                            deltaUnit: '',
                          ),
                        ),
                        SizedBox(
                          width: tileWidth,
                          child: _MetricTile(
                            icon: Icons.fitness_center_rounded,
                            color: AppTheme.primaryBright,
                            label: 'Strength volume',
                            value: '${report.gymVolumeKg.toStringAsFixed(0)} kg',
                            delta: report.gymVolumeKgDelta,
                            deltaUnit: 'kg',
                          ),
                        ),
                        SizedBox(
                          width: tileWidth,
                          child: _MetricTile(
                            icon: Icons.event_available_rounded,
                            color: const Color(0xFFC45BFF),
                            label: 'Workouts logged',
                            value: '${report.gymSessionCount}',
                            delta: report.gymSessionCountDelta?.toDouble(),
                            deltaUnit: '',
                          ),
                        ),
                      ],
                    ),
                    if (report.improvements.isNotEmpty) ...[
                      const SizedBox(height: 20),
                      _ImprovementsCard(improvements: report.improvements),
                    ],
                    const SizedBox(height: 20),
                    _AchievementsCard(future: _achievementsFuture),
                    const SizedBox(height: 20),
                    const _AskSirisCard(),
                  ],
                );
              },
            ),
          );
        },
      ),
    );
  }
}

class _AskSirisCard extends StatefulWidget {
  const _AskSirisCard();

  @override
  State<_AskSirisCard> createState() => _AskSirisCardState();
}

class _AskSirisCardState extends State<_AskSirisCard> {
  final CoachService _service = CoachService();
  final TextEditingController _controller = TextEditingController();
  Future<AskSirisAnswer>? _future;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _submit([String? question]) {
    final value = (question ?? _controller.text).trim();
    if (value.isEmpty) return;
    _controller.text = value;
    setState(() {
      _future = _service.ask(value);
    });
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Ask Siris', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 6),
            Text(
              'Ask a question about your running and gym data.',
              style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant),
            ),
            const SizedBox(height: 14),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _controller,
                    decoration: const InputDecoration(
                      hintText: "e.g. What's my best 5K this year?",
                      isDense: true,
                    ),
                    onSubmitted: _submit,
                  ),
                ),
                const SizedBox(width: 10),
                IconButton.filledTonal(
                  onPressed: () => _submit(),
                  icon: const Icon(Icons.send_rounded),
                  tooltip: 'Ask',
                ),
              ],
            ),
            if (_future != null) ...[
              const SizedBox(height: 16),
              FutureBuilder<AskSirisAnswer>(
                future: _future,
                builder: (context, snapshot) {
                  if (snapshot.connectionState == ConnectionState.waiting) {
                    return const Padding(
                      padding: EdgeInsets.symmetric(vertical: 8),
                      child: SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                    );
                  }
                  if (snapshot.hasError) {
                    return Text(
                      'Could not get an answer.',
                      style: TextStyle(color: Theme.of(context).colorScheme.error),
                    );
                  }
                  final result = snapshot.data!;
                  return _AskSirisResult(result: result, onSuggestionTap: _submit);
                },
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _AskSirisResult extends StatelessWidget {
  const _AskSirisResult({required this.result, required this.onSuggestionTap});

  final AskSirisAnswer result;
  final ValueChanged<String> onSuggestionTap;

  @override
  Widget build(BuildContext context) {
    if (!result.understood) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(result.answer),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: result.suggestions
                .map(
                  (suggestion) => ActionChip(
                    label: Text(suggestion),
                    onPressed: () => onSuggestionTap(suggestion),
                  ),
                )
                .toList(growable: false),
          ),
        ],
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (result.synthesizedAnswer != null)
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.primaryContainer.withValues(alpha: 0.4),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Text(result.synthesizedAnswer!),
          )
        else
          Text(result.answer),
      ],
    );
  }
}

class _TodayCard extends StatelessWidget {
  const _TodayCard({required this.future});

  final Future<TrainingConflictCheck> future;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<TrainingConflictCheck>(
      future: future,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Card(
            child: Padding(
              padding: EdgeInsets.all(20),
              child: SizedBox(
                height: 24,
                child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
              ),
            ),
          );
        }
        if (snapshot.hasError || !snapshot.hasData) {
          return const SizedBox.shrink();
        }
        final check = snapshot.data!;
        final style = _styleFor(context, check.status);
        return Card(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(
                    color: style.color.withValues(alpha: 0.14),
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: Icon(style.icon, color: style.color),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Today', style: Theme.of(context).textTheme.titleMedium),
                      const SizedBox(height: 4),
                      Text(
                        check.guidance,
                        style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  ({IconData icon, Color color}) _styleFor(BuildContext context, TrainingConflictStatus status) =>
      switch (status) {
        TrainingConflictStatus.conflict => (icon: Icons.warning_amber_rounded, color: AppTheme.warning),
        TrainingConflictStatus.reducedRecovery => (
            icon: Icons.battery_2_bar_rounded,
            color: AppTheme.warning
          ),
        TrainingConflictStatus.clear => (icon: Icons.check_circle_outline_rounded, color: AppTheme.success),
        TrainingConflictStatus.insufficientData => (
            icon: Icons.info_outline_rounded,
            color: Theme.of(context).colorScheme.onSurfaceVariant
          ),
      };
}

class _HeadlineCard extends StatelessWidget {
  const _HeadlineCard({required this.report});

  final WeeklyCoachReport report;

  @override
  Widget build(BuildContext context) {
    final combined = report.trainingLoad.combinedIndex;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 52,
              height: 52,
              decoration: BoxDecoration(
                color: AppTheme.primary.withValues(alpha: 0.14),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppTheme.primary.withValues(alpha: 0.35)),
              ),
              child: const Icon(Icons.auto_awesome_rounded, color: AppTheme.primaryBright, size: 26),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(report.headline, style: Theme.of(context).textTheme.titleLarge),
                  const SizedBox(height: 6),
                  Text(
                    _weekRangeLabel(report.weekStart, report.weekEnd),
                    style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant),
                  ),
                ],
              ),
            ),
            if (combined != null) ...[
              const SizedBox(width: 12),
              Text(
                '${combined.round()}',
                style: Theme.of(context)
                    .textTheme
                    .headlineSmall
                    ?.copyWith(fontWeight: FontWeight.w800, color: AppTheme.primaryBright),
              ),
            ],
          ],
        ),
      ),
    );
  }

  String _weekRangeLabel(DateTime start, DateTime end) {
    String label(DateTime d) => '${d.day}/${d.month}';
    return '${label(start)} – ${label(end)}';
  }
}

class _MetricTile extends StatelessWidget {
  const _MetricTile({
    required this.icon,
    required this.color,
    required this.label,
    required this.value,
    required this.delta,
    required this.deltaUnit,
  });

  final IconData icon;
  final Color color;
  final String label;
  final String value;
  final double? delta;
  final String deltaUnit;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Container(
        constraints: const BoxConstraints(minHeight: 140),
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(18),
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [color.withValues(alpha: 0.09), Colors.transparent],
          ),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 38,
                  height: 38,
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.14),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(icon, color: color, size: 20),
                ),
                const SizedBox(width: 10),
                Expanded(child: Text(label, style: Theme.of(context).textTheme.titleSmall)),
              ],
            ),
            const SizedBox(height: 16),
            Text(
              value,
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    color: color,
                    fontWeight: FontWeight.w800,
                  ),
            ),
            const SizedBox(height: 4),
            Text(
              _deltaLabel(),
              style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant, fontSize: 12),
            ),
          ],
        ),
      ),
    );
  }

  String _deltaLabel() {
    if (delta == null) return 'First week logged';
    if (delta == 0) return 'Same as last week';
    final sign = delta! > 0 ? '+' : '';
    final formatted = deltaUnit.isEmpty
        ? '$sign${delta!.round()}'
        : '$sign${delta!.toStringAsFixed(1)} $deltaUnit';
    return '$formatted vs last week';
  }
}

class _AchievementsCard extends StatelessWidget {
  const _AchievementsCard({required this.future});

  final Future<List<Achievement>> future;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<Achievement>>(
      future: future,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Card(
            child: Padding(
              padding: EdgeInsets.all(20),
              child: SizedBox(
                height: 24,
                child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
              ),
            ),
          );
        }
        final achievements = snapshot.data ?? const <Achievement>[];
        if (snapshot.hasError || achievements.isEmpty) {
          return const SizedBox.shrink();
        }
        final unlockedCount = achievements.where((item) => item.unlocked).length;
        return Card(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text('Achievements', style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(width: 8),
                    Text(
                      '$unlockedCount / ${achievements.length}',
                      style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                ...achievements.map((item) => _AchievementRow(achievement: item)),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _AchievementRow extends StatelessWidget {
  const _AchievementRow({required this.achievement});

  final Achievement achievement;

  @override
  Widget build(BuildContext context) {
    final color =
        achievement.unlocked ? AppTheme.success : Theme.of(context).colorScheme.onSurfaceVariant;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            achievement.unlocked ? Icons.emoji_events_rounded : Icons.lock_outline_rounded,
            color: color,
            size: 22,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  achievement.title,
                  style: TextStyle(
                    fontWeight: FontWeight.w700,
                    color: achievement.unlocked
                        ? null
                        : Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  achievement.description,
                  style:
                      TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant, fontSize: 12),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          Text(
            achievement.progressLabel,
            style: TextStyle(fontWeight: FontWeight.w600, color: color, fontSize: 12),
          ),
        ],
      ),
    );
  }
}

class _ImprovementsCard extends StatelessWidget {
  const _ImprovementsCard({required this.improvements});

  final List<ExerciseImprovement> improvements;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('New bests this week', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            ...improvements.map(
              (item) => Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Row(
                  children: [
                    const Text('🏆 ', style: TextStyle(fontSize: 16)),
                    Expanded(
                      child: Text(
                        '${item.exercise} · ${item.recordType.label}: ${item.value.toStringAsFixed(1)} kg (was ${item.previousValue.toStringAsFixed(1)} kg)',
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _CoachError extends StatelessWidget {
  const _CoachError({required this.message, required this.onRetry});

  final String message;
  final Future<void> Function() onRetry;

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.auto_awesome_outlined,
                  size: 54, color: Theme.of(context).colorScheme.onSurfaceVariant),
              const SizedBox(height: 18),
              Text('Coach report unavailable', style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 8),
              Text(message,
                  textAlign: TextAlign.center,
                  style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant)),
              const SizedBox(height: 20),
              FilledButton.icon(
                  onPressed: onRetry,
                  icon: const Icon(Icons.refresh_rounded),
                  label: const Text('Try again')),
            ],
          ),
        ),
      );
}
