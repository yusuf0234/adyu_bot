
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from live_search import get_live_context

question = "Burs başvurusu nasıl yapılır?"
print(f"Soru: {question}")
contexts, sources = get_live_context(question)

print(f"\nBulunan Kaynak Sayısı: {len(sources)}")
for s in sources:
    print(f"- {s}")

print("\n--- İLK 500 KARAKTER BAĞLAM ---")
if contexts:
    # Print a snippet of each context to see if they are empty
    for i, c in enumerate(contexts):
        print(f"\n[Kaynak {i+1}] Uzunluk: {len(c)}")
        print(c[:200] + "...")
else:
    print("BAĞLAM BOŞ!")
