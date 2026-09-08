const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function loadPage(relativePath) {
    const elements = new Map();
    const element = id => {
        if (!elements.has(id)) elements.set(id, {style: {}, files: [], value: '', innerHTML: '', addEventListener() {}});
        return elements.get(id);
    };
    const document = {
        getElementById: element,
        addEventListener() {},
        createElement() {
            return {set textContent(value) {this.innerHTML = String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');}};
        }
    };
    const context = vm.createContext({document, console, setTimeout, clearTimeout});
    const html = fs.readFileSync(path.join(__dirname, relativePath), 'utf8');
    for (const match of html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)) {
        if (match[1].trim()) vm.runInContext(match[1], context, {filename: relativePath});
    }
    return {context, element};
}

async function main() {
    let assertions = 0;
    for (const page of ['index.html', 'HyperBatteryHealthCalc-bat/index.html']) {
        const {context} = loadPage(page);
        const cases = [
            [{minLearnedCapacity: 0, chargeCounter: 4500, batteryLevel: 100}, 4500],
            [{minLearnedCapacity: -1, chargeCounter: 4500, batteryLevel: 100}, 4500],
            [{chargeCounter: 4500, batteryLevel: 100, batteryScale: 200}, null],
            [{chargeCounter: 4500, batteryLevel: 10, batteryScale: 10}, 4500],
            [{chargeCounter: 4500, batteryLevel: 101, batteryScale: 100}, null]
        ];
        for (const [info, expected] of cases) {
            assert.equal(context.getCurrentCapacityInfo(info).value, expected, page);
            assertions++;
        }
        assert.equal(context.parseDurationSeconds('1h2m3s4ms'), 3723.004, page);
        assert.equal(context.parseDurationSeconds('1d2h3m4s'), 93784, page);
        const usage = {};
        context.parseUsageStats('Time on battery: 1d2h3m4s (100.0%) realtime', usage);
        assert.equal(usage.timeOnBatterySeconds, 93784, page);
        assertions += 3;
        const power = {uidPackages:{}};
        context.parsePowerUseStats('UID unrelated: 9999\nGlobal\n    cpu: 9999\n\nEstimated power use (mAh):\n  Capacity: 5000, Computed drain: 600, actual drain: 600\n  Global\n    cpu: 120\n  UID real: 80\n\nUID unrelated-after: 8888\n', power);
        assert.equal(power.topUidPower[0].uid, 'real', page);
        assert.equal(power.powerComponents[0].mah, 120, page);
        assertions += 2;
    }

    const {context, element} = loadPage('HyperBatteryHealthCalc-bat/index.html');
    let closed = 0;
    context.zip = {
        BlobReader: class {constructor(data) {this.data = data;}},
        TextWriter: class {}, BlobWriter: class {},
        ZipReader: class {
            constructor(reader) {this.data = reader.data;}
            async getEntries() {return this.data.getEntries ? this.data.getEntries() : this.data.entries;}
            async close() {closed++;}
        }
    };
    const entry = (filename, text) => ({filename, getData: async () => text});
    const file = {name: 'report.zip', size: 1, entries: [
        entry('bugreport.txt', 'Statistics since last charge:\nEstimated battery capacity: 5000 mAh\nMin learned battery capacity: 4500 mAh\n\n'),
        entry('android.hardware.health.txt', 'batteryFullChargeDesignCapacityUah: 5100000\nbatteryCycleCount: 123\n')
    ]};
    await context.parseZipAndRender(file, 6000);
    assert.match(element('result').innerHTML, /6000/);
    assert.match(element('result').innerHTML, /123/);
    assert.match(element('result').innerHTML, /75\.00/);
    assert.equal(closed, 1);
    assertions += 4;
    await context.parseZipAndRender(file, 5000);
    assert.equal(closed, 1, 'manual recalculation must reuse parsed data');
    assert.match(element('result').innerHTML, /90\.00/);
    assertions += 2;

    const root = loadPage('index.html');
    root.context.zip = context.zip;
    root.element('zip-file').files = [file];
    const beforeRoot = closed;
    await root.context.extractDeviceInfo(file);
    assert.equal(closed - beforeRoot, 1, 'root auto analysis must not decompress a second time');
    root.element('initial-capacity').value = '6000';
    await root.context.calculateBatteryCapacity();
    assert.match(root.element('result').innerHTML, /75\.00/);
    assert.equal(closed - beforeRoot, 1, 'root manual calculation must use cached data');
    assert.equal(root.context.getAutoInitialCapacityCandidate({minLearnedCapacity:4500, lastLearnedCapacity:4600}), null);
    assertions += 4;

    const stats = (design, current=4500) => `Statistics since last charge:\nEstimated battery capacity: ${design} mAh\nMin learned battery capacity: ${current} mAh\n\n`;
    async function choose(page, file) {
        page.element('zip-file').files = [file];
        const original = page.context.extractDeviceInfo || page.context.parseZipAndRender;
        const name = page.context.extractDeviceInfo ? 'extractDeviceInfo' : 'parseZipAndRender';
        let work;
        page.context[name] = (...args) => {work = original(...args); return work;};
        page.context.handleFileSelect();
        page.context[name] = original;
        return work;
    }
    for (const name of ['index.html', 'HyperBatteryHealthCalc-bat/index.html']) {
        const page=loadPage(name);
        page.context.zip=context.zip;
        await choose(page,{name:'valid.zip',size:1,entries:[
            entry('android.hardware.health-a.txt','batteryFullChargeDesignCapacityUah: 5000000\n'),
            entry('android.hardware.health-b.txt','batteryFullChargeDesignCapacityUah: 0\n'),
            entry('bugreport.txt',stats(5000))
        ]});
        assert.match(page.element('result').innerHTML,/90\.00%/, name);
        await choose(page,{name:'partial.zip',size:1,entries:[entry('bugreport.txt','[ro.product.model]: [Snapshot Device]\nCurrent Battery Service state:\nlevel: 20\nscale: 100\nCharge counter: 1000000\ntemperature: 345\n\n'+stats(5000,0))]});
        assert.match(page.element('result').innerHTML,/34\.5/,name);
        assert.match(page.element('result').innerHTML,/1000 mAh/,name);
        let release;
        const old = choose(page,{name:'old.zip',size:1,entries:[{filename:'bugreport.txt',getData:()=>new Promise(resolve=>{release=resolve;})}]});
        for(let i=0;i<10&&!release;i++) await Promise.resolve();
        assert.ok(release);
        await choose(page,{name:'new.zip',size:1,entries:[entry('bugreport.txt','[ro.product.model]: [New Device]\n'+stats(5000))]});
        const expected=page.element('result').innerHTML;
        release('[ro.product.model]: [Old Device]\n'+stats(5000,4000));
        await old;
        assert.equal(page.element('result').innerHTML,expected,name);
        assertions += 5;
    }
    const retry=loadPage('index.html');
    retry.context.zip=context.zip;
    let attempts=0, releaseRetry;
    const failedFile={name:'retry.zip',size:1,getEntries(){if(++attempts===1) throw new Error('initial failure');return new Promise(resolve=>{releaseRetry=resolve;});}};
    await choose(retry,failedFile);
    retry.element('initial-capacity').value='5000';
    const pendingRetry=retry.context.processZipFile(failedFile,5000);
    assert.ok(releaseRetry);
    await choose(retry,{name:'new.zip',size:1,entries:[entry('bugreport.txt','[ro.product.model]: [New Device]\n'+stats(5000))]});
    const expected=retry.element('result').innerHTML;
    releaseRetry([]);
    await pendingRetry;
    assert.equal(retry.element('result').innerHTML,expected,'stale manual retry replaced current report');
    assertions += 2;
    const partialRetry=loadPage('index.html');
    partialRetry.context.zip=context.zip;
    await partialRetry.context.processZipFile({name:'partial.zip',size:1,entries:[entry('bugreport.txt','[ro.product.model]: [Partial Retry]\nCurrent Battery Service state:\nlevel: 20\nscale: 100\nCharge counter: 1000000\ntemperature: 345\n\n'+stats(5000,0))]},5000);
    assert.match(partialRetry.element('result').innerHTML,/34\.5/);
    assert.match(partialRetry.element('result').innerHTML,/1000 mAh/);
    assertions += 2;
    console.log(`PASS: ${assertions} browser-logic assertions`);
}
main().catch(error => {console.error(error); process.exitCode = 1;});
