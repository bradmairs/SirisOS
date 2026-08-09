import 'package:flutter/material.dart';

/// SirisOS branding.
///
/// Uses the repository branding asset directly. The fallback is deliberately
/// visible so a missing/undecodable asset can never leave the logo area blank.
class SirisLogo extends StatelessWidget {
  const SirisLogo({this.size = 56, this.showWordmark = true, super.key});

  final double size;
  final bool showWordmark;

  static const _logoAsset = 'assets/branding/siris_logo_red.webp';

  @override
  Widget build(BuildContext context) {
    final width = showWordmark ? size * 2.25 : size;

    return Semantics(
      label: 'SirisOS',
      image: true,
      child: SizedBox(
        width: width,
        child: Image.asset(
          _logoAsset,
          width: width,
          fit: BoxFit.fitWidth,
          alignment: Alignment.topCenter,
          filterQuality: FilterQuality.high,
          gaplessPlayback: true,
          errorBuilder: (context, error, stackTrace) =>
              _VisibleFallback(width: width, showWordmark: showWordmark),
        ),
      ),
    );
  }
}

class _VisibleFallback extends StatelessWidget {
  const _VisibleFallback({required this.width, required this.showWordmark});

  final double width;
  final bool showWordmark;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: width,
          height: width,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            border: Border.all(color: const Color(0xFFFF2638), width: 2),
            boxShadow: const [
              BoxShadow(color: Color(0x66FF1027), blurRadius: 18),
            ],
          ),
          alignment: Alignment.center,
          child: Text(
            'S',
            style: TextStyle(
              color: const Color(0xFFFF2638),
              fontSize: width * .58,
              fontWeight: FontWeight.w900,
              fontStyle: FontStyle.italic,
              height: 1,
              shadows: const [Shadow(color: Color(0xFFFF1027), blurRadius: 12)],
            ),
          ),
        ),
        if (showWordmark) ...[
          const SizedBox(height: 8),
          Container(width: width * .62, height: 2, color: const Color(0xFFFF2638)),
          const SizedBox(height: 6),
          Text(
            'OS',
            style: TextStyle(
              color: const Color(0xFFE7E7EA),
              fontSize: width * .18,
              fontWeight: FontWeight.w700,
              letterSpacing: width * .025,
            ),
          ),
        ],
      ],
    );
  }
}
