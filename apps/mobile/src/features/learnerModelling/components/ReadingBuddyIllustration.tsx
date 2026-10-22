import { StyleSheet, Text, View } from "react-native";

import { palette, radii } from "../theme";

interface ReadingBuddyIllustrationProps {
  compact?: boolean;
  large?: boolean;
}

export function ReadingBuddyIllustration({ compact = false, large = false }: ReadingBuddyIllustrationProps) {
  return (
    <View
      accessibilityLabel="ReadBuddy smiling book character"
      accessible
      accessibilityRole="image"
      style={[styles.frame, compact && styles.compactFrame, large && styles.largeFrame]}
    >
      <View style={styles.sparkleOne} />
      <View style={styles.sparkleTwo} />
      {large ? <View style={styles.ground} /> : null}
      <View style={[styles.book, compact && styles.compactBook, large && styles.largeBook]}>
        <View style={styles.page}>
          <Text allowFontScaling={false} style={styles.letters}>Aa</Text>
          <View style={styles.eyeRow}>
            <View style={styles.eye} />
            <View style={styles.eye} />
          </View>
          <View style={styles.smile} />
        </View>
        <View style={[styles.page, styles.rightPage]}>
          <View style={styles.storyLineLong} />
          <View style={styles.storyLine} />
          <View style={styles.storyLineShort} />
        </View>
        <View style={styles.spine} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  largeFrame: {
    width: 220,
    height: 170,
    borderRadius: 32,
    backgroundColor: palette.primarySoft,
    transform: [{ rotate: "0deg" }],
  },
  largeBook: {
    transform: [{ rotate: "-4deg" }, { scale: 1.7 }],
  },
  ground: {
    position: "absolute",
    bottom: 15,
    width: 120,
    height: 12,
    borderRadius: 60,
    backgroundColor: "#BDE7D7",
  },
  frame: {
    width: 126,
    height: 112,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: radii.large,
    backgroundColor: palette.yellowSoft,
    transform: [{ rotate: "2deg" }],
  },
  compactFrame: {
    width: 94,
    height: 84,
  },
  book: {
    width: 94,
    height: 66,
    flexDirection: "row",
    transform: [{ rotate: "-3deg" }],
  },
  compactBook: {
    transform: [{ rotate: "-3deg" }, { scale: 0.78 }],
  },
  page: {
    flex: 1,
    alignItems: "center",
    borderBottomLeftRadius: 13,
    borderTopLeftRadius: 9,
    backgroundColor: palette.surface,
    paddingTop: 7,
  },
  rightPage: {
    alignItems: "flex-start",
    borderBottomLeftRadius: 0,
    borderBottomRightRadius: 13,
    borderTopLeftRadius: 0,
    borderTopRightRadius: 9,
    paddingHorizontal: 8,
    paddingTop: 14,
  },
  spine: {
    position: "absolute",
    left: 46,
    top: 3,
    width: 2,
    height: 61,
    borderRadius: 2,
    backgroundColor: "#E4D9C9",
  },
  letters: {
    color: palette.primary,
    fontSize: 14,
    fontWeight: "900",
  },
  eyeRow: {
    flexDirection: "row",
    gap: 10,
    marginTop: 5,
  },
  eye: {
    width: 4,
    height: 5,
    borderRadius: 3,
    backgroundColor: palette.ink,
  },
  smile: {
    width: 13,
    height: 7,
    borderBottomWidth: 2,
    borderColor: palette.coral,
    borderRadius: 7,
  },
  storyLineLong: {
    width: 30,
    height: 5,
    borderRadius: 3,
    backgroundColor: palette.teal,
  },
  storyLine: {
    width: 24,
    height: 5,
    borderRadius: 3,
    backgroundColor: palette.coral,
    marginTop: 7,
  },
  storyLineShort: {
    width: 17,
    height: 5,
    borderRadius: 3,
    backgroundColor: palette.primary,
    marginTop: 7,
  },
  sparkleOne: {
    position: "absolute",
    right: 10,
    top: 10,
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: palette.coral,
  },
  sparkleTwo: {
    position: "absolute",
    bottom: 12,
    left: 9,
    width: 8,
    height: 8,
    transform: [{ rotate: "45deg" }],
    backgroundColor: palette.primary,
  },
});
