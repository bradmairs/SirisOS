import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

enum SirisStatus { neutral, info, success, warning, critical }

class SirisCard extends StatelessWidget {
  const SirisCard({
    required this.child,
    this.padding = const EdgeInsets.all(20),
    this.accent,
    this.emphasised = false,
    super.key,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final Color? accent;
  final bool emphasised;

  @override
  Widget build(BuildContext context) {
    final highlight = accent ?? Theme.of(context).colorScheme.primary;
    return Container(
      padding: padding,
      decoration: BoxDecoration(
        color: AppTheme.surface.withValues(alpha: 0.96),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: emphasised
              ? highlight.withValues(alpha: 0.72)
              : AppTheme.border,
        ),
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            highlight.withValues(alpha: emphasised ? 0.13 : 0.07),
            AppTheme.surface.withValues(alpha: 0.96),
          ],
        ),
        boxShadow: [
          BoxShadow(
            color: highlight.withValues(alpha: emphasised ? 0.12 : 0.05),
            blurRadius: emphasised ? 34 : 24,
            spreadRadius: -10,
          ),
        ],
      ),
      child: child,
    );
  }
}

class SirisPanel extends StatelessWidget {
  const SirisPanel({
    required this.title,
    required this.child,
    this.subtitle,
    this.icon,
    this.trailing,
    this.accent,
    super.key,
  });

  final String title;
  final String? subtitle;
  final IconData? icon;
  final Widget child;
  final Widget? trailing;
  final Color? accent;

  @override
  Widget build(BuildContext context) => SirisCard(
        accent: accent,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                if (icon != null) ...[
                  Icon(icon, size: 20, color: accent ?? Theme.of(context).colorScheme.primary),
                  const SizedBox(width: 10),
                ],
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(title, style: Theme.of(context).textTheme.titleMedium),
                      if (subtitle != null)
                        Text(
                          subtitle!,
                          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                color: Theme.of(context).colorScheme.onSurfaceVariant,
                              ),
                        ),
                    ],
                  ),
                ),
                if (trailing != null) trailing!,
              ],
            ),
            const SizedBox(height: 18),
            child,
          ],
        ),
      );
}

class SirisMetric extends StatelessWidget {
  const SirisMetric({
    required this.label,
    required this.value,
    this.detail,
    this.icon,
    this.accent,
    super.key,
  });

  final String label;
  final String value;
  final String? detail;
  final IconData? icon;
  final Color? accent;

  @override
  Widget build(BuildContext context) {
    final color = accent ?? Theme.of(context).colorScheme.primary;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            if (icon != null) ...[
              Icon(icon, size: 17, color: color),
              const SizedBox(width: 7),
            ],
            Text(
              label.toUpperCase(),
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    letterSpacing: 1.2,
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
            ),
          ],
        ),
        const SizedBox(height: 7),
        Text(
          value,
          style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                color: color,
                fontWeight: FontWeight.w800,
              ),
        ),
        if (detail != null) ...[
          const SizedBox(height: 4),
          Text(
            detail!,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
          ),
        ],
      ],
    );
  }
}

class SirisStatusChip extends StatelessWidget {
  const SirisStatusChip({
    required this.label,
    this.status = SirisStatus.neutral,
    this.icon,
    super.key,
  });

  final String label;
  final SirisStatus status;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    final color = _statusColor(context, status);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withValues(alpha: 0.34)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon ?? Icons.circle, size: icon == null ? 8 : 15, color: color),
          const SizedBox(width: 7),
          Text(
            label,
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: color,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 0.4,
                ),
          ),
        ],
      ),
    );
  }

  static Color _statusColor(BuildContext context, SirisStatus status) => switch (status) {
        SirisStatus.neutral => Theme.of(context).colorScheme.onSurfaceVariant,
        SirisStatus.info => AppTheme.info,
        SirisStatus.success => AppTheme.success,
        SirisStatus.warning => AppTheme.warning,
        SirisStatus.critical => Theme.of(context).colorScheme.error,
      };
}

class SirisGauge extends StatelessWidget {
  const SirisGauge({
    required this.value,
    required this.label,
    this.size = 92,
    this.accent,
    super.key,
  });

  final double value;
  final String label;
  final double size;
  final Color? accent;

  @override
  Widget build(BuildContext context) {
    final safeValue = value.clamp(0.0, 1.0).toDouble();
    final color = accent ?? Theme.of(context).colorScheme.primary;
    return SizedBox(
      width: size,
      height: size,
      child: Stack(
        alignment: Alignment.center,
        children: [
          SizedBox.expand(
            child: CircularProgressIndicator(
              value: safeValue,
              strokeWidth: 7,
              backgroundColor: AppTheme.surfaceRaised,
              color: color,
              strokeCap: StrokeCap.round,
            ),
          ),
          Text(
            label,
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800),
          ),
        ],
      ),
    );
  }
}

class SirisTimeline extends StatelessWidget {
  const SirisTimeline({required this.items, super.key});

  final List<SirisTimelineItem> items;

  @override
  Widget build(BuildContext context) => Column(
        children: items
            .map<Widget>(
              (item) => Padding(
                padding: const EdgeInsets.only(bottom: 14),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Padding(
                      padding: const EdgeInsets.only(top: 5),
                      child: Container(
                        width: 8,
                        height: 8,
                        decoration: BoxDecoration(
                          color: item.accent ?? Theme.of(context).colorScheme.primary,
                          shape: BoxShape.circle,
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(item.title, style: Theme.of(context).textTheme.bodyMedium),
                          if (item.detail != null)
                            Text(
                              item.detail!,
                              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                                  ),
                            ),
                        ],
                      ),
                    ),
                    if (item.trailing != null)
                      Text(
                        item.trailing!,
                        style: Theme.of(context).textTheme.labelSmall?.copyWith(
                              color: Theme.of(context).colorScheme.onSurfaceVariant,
                            ),
                      ),
                  ],
                ),
              ),
            )
            .toList(growable: false),
      );
}

class SirisTimelineItem {
  const SirisTimelineItem({
    required this.title,
    this.detail,
    this.trailing,
    this.accent,
  });

  final String title;
  final String? detail;
  final String? trailing;
  final Color? accent;
}
