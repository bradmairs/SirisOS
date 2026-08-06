import 'package:flutter/material.dart';

import '../core/siris_score.dart';
import '../models/dashboard_summary.dart';

class SirisScorePanel extends StatelessWidget {
  const SirisScorePanel({required this.dashboard, super.key});

  final DashboardSummary dashboard;

  @override
  Widget build(BuildContext context) {
    final result = const DeterministicSirisScore().calculate(dashboard);
    final strongest = [...result.contributions]
      ..sort((a, b) => b.score.compareTo(a.score));
    final weakest = [...result.contributions]
      ..sort((a, b) => a.score.compareTo(b.score));

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.insights_rounded),
                const SizedBox(width: 10),
                Text('Siris Score', style: Theme.of(context).textTheme.titleLarge),
                const Spacer(),
                Text(
                  '${result.score}',
                  style: Theme.of(context).textTheme.displaySmall?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            LinearProgressIndicator(value: result.score / 100),
            const SizedBox(height: 16),
            Text('Supporting today', style: Theme.of(context).textTheme.labelLarge),
            const SizedBox(height: 6),
            Text(strongest.first.explanation),
            const SizedBox(height: 12),
            Text('Needs attention', style: Theme.of(context).textTheme.labelLarge),
            const SizedBox(height: 6),
            Text(weakest.first.explanation),
          ],
        ),
      ),
    );
  }
}
