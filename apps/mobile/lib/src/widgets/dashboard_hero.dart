import 'package:flutter/material.dart';

import '../core/notification_policy.dart';
import '../core/siris_score.dart';
import '../models/dashboard_summary.dart';
import '../theme/app_theme.dart';

class DashboardHero extends StatelessWidget {
  const DashboardHero({
    required this.greeting,
    required this.data,
    super.key,
  });

  final String greeting;
  final DashboardSummary data;

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width;
    final wide = width >= 980;
    final policyItems = NotificationPolicyEngine.instance.activeOutcomes
        .map((outcome) => outcome.rule.message);
    final items = <String>{
      ...policyItems,
      ...data.briefingItems,
    }.take(4).toList(growable: false);

    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: AppTheme.border),
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF180D0F), Color(0xFF0D090A)],
        ),
        boxShadow: const [
          BoxShadow(
            color: Color(0x33E5484D),
            blurRadius: 30,
            spreadRadius: -12,
          ),
        ],
      ),
      padding: EdgeInsets.all(wide ? 28 : 22),
      child: wide
          ? Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                Expanded(child: _Briefing(greeting: greeting, data: data, items: items)),
                const SizedBox(width: 28),
                _ScoreGauge(score: _score(data)),
              ],
            )
          : Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _Briefing(greeting: greeting, data: data, items: items),
                const SizedBox(height: 24),
                Align(alignment: Alignment.center, child: _ScoreGauge(score: _score(data))),
              ],
            ),
    );
  }

  int _score(DashboardSummary data) =>
      const DeterministicSirisScore().calculate(data).score;
}

class _Briefing extends StatelessWidget {
  const _Briefing({required this.greeting, required this.data, required this.items});

  final String greeting;
  final DashboardSummary data;
  final List<String> items;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Container(
              width: 54,
              height: 54,
              decoration: const BoxDecoration(
                shape: BoxShape.circle,
                gradient: LinearGradient(colors: [AppTheme.primary, AppTheme.primaryBright]),
                boxShadow: [BoxShadow(color: Color(0x55E5484D), blurRadius: 18)],
              ),
              child: const Icon(Icons.auto_awesome_rounded, color: Colors.white),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('$greeting, ${data.greetingName}.', style: Theme.of(context).textTheme.headlineSmall),
                  const SizedBox(height: 4),
                  Text("Here’s what’s happening with SirisOS.", style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant)),
                ],
              ),
            ),
          ],
        ),
        const SizedBox(height: 24),
        if (items.isEmpty)
          const Text('Everything is quiet right now.')
        else
          ...items.map(
            (item) => Padding(
              padding: const EdgeInsets.only(bottom: 13),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    margin: const EdgeInsets.only(top: 3),
                    width: 28,
                    height: 28,
                    decoration: BoxDecoration(
                      color: AppTheme.primary.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(9),
                    ),
                    child: const Icon(Icons.check_rounded, size: 17, color: AppTheme.primaryBright),
                  ),
                  const SizedBox(width: 12),
                  Expanded(child: Text(item)),
                ],
              ),
            ),
          ),
      ],
    );
  }
}

class _ScoreGauge extends StatelessWidget {
  const _ScoreGauge({required this.score});

  final int score;

  @override
  Widget build(BuildContext context) {
    final label = score >= 90 ? 'Excellent' : score >= 75 ? 'Good' : score >= 60 ? 'Fair' : 'Needs attention';
    return SizedBox(
      width: 210,
      height: 210,
      child: Stack(
        alignment: Alignment.center,
        children: [
          SizedBox(
            width: 178,
            height: 178,
            child: CircularProgressIndicator(
              value: score / 100,
              strokeWidth: 12,
              backgroundColor: AppTheme.border,
              color: AppTheme.primaryBright,
              strokeCap: StrokeCap.round,
            ),
          ),
          Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('SirisOS Score', style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant)),
              const SizedBox(height: 4),
              Text('$score', style: Theme.of(context).textTheme.displayMedium?.copyWith(fontWeight: FontWeight.w800)),
              Text(label, style: const TextStyle(color: AppTheme.success, fontWeight: FontWeight.w700)),
            ],
          ),
        ],
      ),
    );
  }
}
