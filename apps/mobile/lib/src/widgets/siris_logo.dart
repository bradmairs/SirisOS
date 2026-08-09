import 'package:flutter/material.dart';

/// SirisOS branding.
///
/// IMPORTANT: the approved artwork is rendered directly. Do not recreate the
/// S with Flutter paths or typography: that changes its geometry, bevels,
/// lighting and proportions.
class SirisLogo extends StatelessWidget {
  const SirisLogo({this.size = 56, this.showWordmark = true, super.key});

  final double size;
  final bool showWordmark;

  static const _approvedLogo = 'assets/branding/siris_logo_red.webp';

  @override
  Widget build(BuildContext context) {
    // The approved source artwork is 468 x 667. Preserve that aspect ratio and
    // show the complete image rather than clipping/cropping the S or OS.
    final width = showWordmark ? size * 2.25 : size;
    final height = width * (667 / 468);

    return Semantics(
      label: 'SirisOS',
      image: true,
      child: SizedBox(
        width: width,
        height: height,
        child: Image.asset(
          _approvedLogo,
          width: width,
          height: height,
          fit: BoxFit.contain,
          alignment: Alignment.center,
          filterQuality: FilterQuality.high,
          gaplessPlayback: true,
          errorBuilder: (context, error, stackTrace) => const SizedBox.shrink(),
        ),
      ),
    );
  }
}
