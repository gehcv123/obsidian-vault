#!/bin/bash
# Auto-organize hook for Claude Code
# Reads the file path from the Edit/Write tool event and moves if needed

VAULT="C:/Users/Administrator/Desktop/Akiva's life"

# Read the tool result from stdin (JSON with file_path)
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | node -e "
  const chunks = [];
  process.stdin.on('data', c => chunks.push(c));
  process.stdin.on('end', () => {
    try {
      const d = JSON.parse(chunks.join(''));
      console.log(d.file_path || '');
    } catch(e) { console.log(''); }
  });
" 2>/dev/null)

# Only process .md files in the vault root (not already in subfolders)
if [[ -z "$FILE_PATH" ]]; then exit 0; fi
if [[ "$FILE_PATH" != *.md ]]; then exit 0; fi
if [[ "$FILE_PATH" != "$VAULT/"* ]]; then exit 0; fi

# Skip files already in subdirectories, Templates, Scripts
REL="${FILE_PATH#$VAULT/}"
if [[ "$REL" == */* ]]; then exit 0; fi

# Read first 20 lines to check frontmatter and tags
CONTENT=$(head -20 "$FILE_PATH" 2>/dev/null)
BASENAME=$(basename "$FILE_PATH")

TARGET=""

# Check filename pattern: YYYY-MM-DD.md → Journal/
if [[ "$BASENAME" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}\.md$ ]]; then
  TARGET="Journal"
fi

# Check filename pattern: YYYY-Www.md → Journal/
if [[ "$BASENAME" =~ ^[0-9]{4}-W[0-9]{2}\.md$ ]]; then
  TARGET="Journal"
fi

# Check tags in content
if echo "$CONTENT" | grep -qE '(tags:.*daily|#daily)'; then
  TARGET="Journal"
elif echo "$CONTENT" | grep -qE '(tags:.*weekly|#weekly)'; then
  TARGET="Journal"
elif echo "$CONTENT" | grep -qE '(tags:.*project|#project)'; then
  TARGET="Projects"
elif echo "$CONTENT" | grep -qE '(tags:.*reference|#reference)'; then
  TARGET="References"
fi

if [[ -n "$TARGET" ]]; then
  mkdir -p "$VAULT/$TARGET"
  mv "$FILE_PATH" "$VAULT/$TARGET/$BASENAME"
  echo "Moved $BASENAME → $TARGET/"
fi
