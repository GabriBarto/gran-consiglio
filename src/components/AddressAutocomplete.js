import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { searchAddresses } from '../api/places';
import { colors, radius, spacing } from '../theme';
import FormField from './FormField';

// Campo indirizzo con suggerimenti (Photon / OpenStreetMap). Quando il venditore sceglie
// un suggerimento chiama `onSelect({ address, lat, lng })`; se invece modifica
// il testo a mano chiama `onChangeText` (e il form deve invalidare le
// coordinate precedenti).
export default function AddressAutocomplete({ label, placeholder, value, onChangeText, onSelect }) {
  const [suggestions, setSuggestions] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const skipNextSearch = useRef(false);

  useEffect(() => {
    if (skipNextSearch.current) {
      skipNextSearch.current = false;
      return;
    }
    const query = value.trim();
    if (query.length < 3) {
      setSuggestions([]);
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setIsLoading(true);
      setError(null);
      try {
        setSuggestions(await searchAddresses(query, controller.signal));
      } catch (err) {
        if (err.name !== 'AbortError') setError(err.message);
      } finally {
        if (!controller.signal.aborted) setIsLoading(false);
      }
    }, 350);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [value]);

  function handlePick(place) {
    setSuggestions([]);
    skipNextSearch.current = true;
    onSelect(place);
  }

  return (
    <View>
      <FormField
        label={label}
        placeholder={placeholder}
        value={value}
        onChangeText={onChangeText}
        autoCapitalize="words"
        error={error}
      />
      {isLoading ? <ActivityIndicator style={styles.loader} color={colors.primary} /> : null}
      {suggestions.length > 0 ? (
        <View style={styles.list}>
          {suggestions.map((s) => (
            <Pressable key={s.id} style={styles.item} onPress={() => handlePick(s)}>
              <Text style={styles.itemText}>📍 {s.text}</Text>
            </Pressable>
          ))}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  loader: { alignSelf: 'flex-start', marginBottom: spacing.sm },
  list: {
    marginTop: -spacing.sm,
    marginBottom: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  item: {
    padding: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  itemText: { color: colors.text },
});
