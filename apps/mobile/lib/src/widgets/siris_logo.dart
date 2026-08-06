import 'package:flutter/material.dart';

class SirisLogo extends StatelessWidget {
  const SirisLogo({this.size = 56, this.showWordmark = true, super.key});

  final double size;
  final bool showWordmark;

  @override
  Widget build(BuildContext context) {
    final primary = Theme.of(context).colorScheme.primary;
    final mark = Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF2563EB), Color(0xFF38BDF8)],
        ),
        boxShadow: [
          BoxShadow(
            color: primary.withValues(alpha: 0.35),
            blurRadius: 24,
            spreadRadius: 1,
          ),
        ],
      ),
      padding: EdgeInsets.all(size * 0.09),
      child: Container(
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: const Color(0xFF07111F),
          border: Border.all(color: const Color(0xFF60A5FA), width: 2),
        ),
        alignment: Alignment.center,
        child: Text(
          'S',
          style: TextStyle(
            fontSize: size * 0.48,
            fontWeight: FontWeight.w800,
            height: 1,
            letterSpacing: -2,
            color: Colors.white,
          ),
        ),
      ),
    );

    if (!showWordmark) return mark;
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        mark,
        const SizedBox(height: 12),
        RichText(
          text: TextSpan(
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.w800,
                  letterSpacing: 2.2,
                ),
            children: const [
              TextSpan(text: 'SIRIS', style: TextStyle(color: Colors.white)),
              TextSpan(text: 'OS', style: TextStyle(color: Color(0xFF38BDF8))),
            ],
          ),
        ),
        const SizedBox(height: 4),
        Text(
          'Your personal OS',
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: const Color(0xFF8292A8),
              ),
        ),
      ],
    );
  }
}
