import { forwardRef } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text } from 'react-native';
import { colors, radius, spacing } from '../theme';

// forwardRef so this can be used as the child of expo-router's <Link asChild>,
// which needs to attach a ref to whatever it wraps.
const PrimaryButton = forwardRef(function PrimaryButton(
  { title, onPress, loading, disabled, variant = 'solid', style },
  ref
) {
  const isOutline = variant === 'outline';
  return (
    <Pressable
      ref={ref}
      onPress={onPress}
      disabled={disabled || loading}
      style={({ pressed }) => [
        styles.button,
        isOutline ? styles.outline : styles.solid,
        (disabled || loading) && styles.disabled,
        pressed && !disabled && !loading && styles.pressed,
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={isOutline ? colors.primary : '#fff'} />
      ) : (
        <Text style={[styles.text, isOutline && styles.outlineText]}>{title}</Text>
      )}
    </Pressable>
  );
});

export default PrimaryButton;

const styles = StyleSheet.create({
  button: {
    borderRadius: radius.sm,
    paddingVertical: spacing.md - 2,
    alignItems: 'center',
    justifyContent: 'center',
  },
  solid: {
    backgroundColor: colors.primary,
  },
  outline: {
    backgroundColor: 'transparent',
    borderWidth: 1.5,
    borderColor: colors.primary,
  },
  disabled: {
    opacity: 0.6,
  },
  pressed: {
    opacity: 0.85,
  },
  text: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '700',
  },
  outlineText: {
    color: colors.primary,
  },
});
